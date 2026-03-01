"""Chat router for the conversational video library agent."""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.chat import ChatMessageRequest, ChatNewSessionResponse
from app.services.agent_service import AgentService
from app.redis_client import get_redis

router = APIRouter(prefix="/chat")


@router.post("/new", response_model=ChatNewSessionResponse)
async def create_session(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Create a new chat session and return its ID."""
    session_id = str(uuid.uuid4())
    redis_client = get_redis()

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    session_data = {
        "session_id": session_id,
        "created_at": now,
        "last_message_at": now,
        "message_count": 0,
    }
    redis_client.set(
        f"chat:{current_user.id}:{session_id}",
        json.dumps(session_data),
        expire=3600,
    )

    return ChatNewSessionResponse(session_id=session_id)


@router.post("/message")
async def send_message(
    request: ChatMessageRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Send a message to the chat agent and stream the response via SSE.

    The agent may execute tool calls (search, filter, stats, create playlist)
    before returning a final text response.
    """
    agent = AgentService(user_id=current_user.id, db=db)

    async def event_stream():
        async for event in agent.chat(request.session_id, request.message):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions")
async def list_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """List active chat sessions for the current user."""
    redis_client = get_redis()

    # Scan for session keys
    sessions = []
    if redis_client.client:
        pattern = f"chat:{current_user.id}:*"
        cursor = 0
        while True:
            cursor, keys = redis_client.client.scan(
                cursor=cursor, match=pattern, count=100
            )
            for key in keys:
                data = redis_client.get(key)
                if data:
                    session_data = json.loads(data)
                    # Only include sessions with actual data
                    if session_data.get("session_id"):
                        sessions.append(
                            {
                                "session_id": session_data["session_id"],
                                "created_at": session_data.get("created_at"),
                                "last_message_at": session_data.get("last_message_at"),
                                "message_count": session_data.get("message_count", 0),
                            }
                        )
            if cursor == 0:
                break

    # Sort by last_message_at descending
    sessions.sort(key=lambda s: s.get("last_message_at", ""), reverse=True)

    return sessions


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Delete a chat session."""
    redis_client = get_redis()
    key = f"chat:{current_user.id}:{session_id}"

    if not redis_client.exists(key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    redis_client.delete(key)
    return {"status": "deleted", "session_id": session_id}
