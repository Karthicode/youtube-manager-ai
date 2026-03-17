"""Chat router for the conversational video library agent."""

from __future__ import annotations

import json
import uuid
from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatNewSessionResponse,
    ChatSession as ChatSessionSchema,
)
from app.services.agent_service import AgentService
from app.redis_client import get_redis
from app.utils.cache_invalidation import invalidate_chat_sessions

router = APIRouter(prefix="/chat")


SESSIONS_CACHE_TTL = 300  # 5 minutes


@router.post("/new", response_model=ChatNewSessionResponse)
def create_session(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a new chat session and return its ID."""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.add(
        ChatSession(
            id=session_id,
            user_id=current_user.id,
            title="New Chat",
            created_at=now,
            updated_at=now,
            last_message_at=now,
            message_count=0,
        )
    )
    db.commit()
    invalidate_chat_sessions(current_user.id)

    return ChatNewSessionResponse(session_id=session_id)


@router.post("/message")
async def send_message(
    request: ChatMessageRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Send a message to the chat agent and stream the response as JSON Lines.

    The agent may execute tool calls (search, filter, stats, create playlist)
    before returning a final text response.
    """
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == request.session_id, ChatSession.user_id == current_user.id
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    now = datetime.now(timezone.utc)
    if not session.title or session.title == "New Chat":
        trimmed = request.message.strip()
        session.title = (trimmed[:60] + "...") if len(trimmed) > 60 else trimmed

    db.add(
        ChatMessage(
            session_id=request.session_id,
            role="user",
            content=request.message,
            created_at=now,
        )
    )
    session.last_message_at = now
    session.message_count += 1
    db.commit()
    invalidate_chat_sessions(current_user.id)

    agent = AgentService(user_id=current_user.id, db=db)

    async def event_stream():
        assistant_content = ""
        tool_calls: list[dict] = []
        tool_results: list[dict] = []

        async for event in agent.chat(request.session_id, request.message):
            event_type = event.type
            if event_type == "message":
                assistant_content = event.content or ""
            elif event_type == "error" and not assistant_content:
                assistant_content = (
                    event.content or "Sorry, something went wrong. Please try again."
                )
            elif event_type == "tool_call":
                tool_calls.append(
                    {
                        "tool": event.tool,
                        "arguments": event.arguments or {},
                    }
                )
            elif event_type == "tool_result":
                tool_results.append(
                    {
                        "tool": event.tool,
                        "result": event.result,
                    }
                )

            yield event.model_dump_json(exclude_none=True) + "\n"

        if assistant_content or tool_calls or tool_results:
            persisted_content = assistant_content or "No response content"
            db.add(
                ChatMessage(
                    session_id=request.session_id,
                    role="assistant",
                    content=persisted_content,
                    tool_calls_json=json.dumps(tool_calls) if tool_calls else None,
                    tool_results_json=(
                        json.dumps(tool_results) if tool_results else None
                    ),
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.message_count += 1
            session.last_message_at = datetime.now(timezone.utc)
            db.commit()

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions", response_model=list[ChatSessionSchema])
def list_sessions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """List chat sessions for the current user (persisted in DB)."""
    redis = get_redis()
    cache_key = f"chat_sessions:{current_user.id}"

    cached = redis.get(cache_key)
    if cached:
        return [ChatSessionSchema.model_validate(s) for s in json.loads(cached)]

    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.last_message_at.desc())
        .all()
    )
    result = [
        ChatSessionSchema(
            session_id=s.id,
            title=s.title,
            created_at=s.created_at,
            last_message_at=s.last_message_at,
            message_count=s.message_count,
        )
        for s in sessions
    ]
    redis.set(
        cache_key,
        json.dumps([r.model_dump(mode="json") for r in result]),
        expire=SESSIONS_CACHE_TTL,
    )
    return result


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
def get_session_messages(
    session_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Fetch persisted messages for a chat session."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )

    result: list[ChatMessageResponse] = []
    for message in messages:
        try:
            tool_calls = (
                json.loads(message.tool_calls_json) if message.tool_calls_json else []
            )
        except Exception:
            tool_calls = []
        try:
            tool_results = (
                json.loads(message.tool_results_json)
                if message.tool_results_json
                else []
            )
        except Exception:
            tool_results = []

        result.append(
            ChatMessageResponse(
                id=message.id,
                role=message.role,
                content=message.content,
                tool_calls=tool_calls,
                tool_results=tool_results,
                created_at=message.created_at,
            )
        )
    return result


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Delete a chat session."""
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    redis_client = get_redis()
    # Invalidate the sessions list cache so stale entries aren't shown.
    invalidate_chat_sessions(current_user.id)
    # Best-effort cleanup of legacy Redis session key.
    redis_client.delete(f"chat:{current_user.id}:{session_id}")

    if not session:
        # Idempotent: session already gone, nothing to do.
        return {"status": "deleted", "session_id": session_id}

    db.delete(session)
    db.commit()

    return {"status": "deleted", "session_id": session_id}
