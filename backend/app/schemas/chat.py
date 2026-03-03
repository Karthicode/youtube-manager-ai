"""Schemas for the conversational video library agent."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    """Request to send a message to the chat agent."""

    session_id: str
    message: str


class ChatNewSessionResponse(BaseModel):
    """Response when creating a new chat session."""

    session_id: str


class ChatSession(BaseModel):
    """Metadata for a chat session."""

    session_id: str
    title: str | None = None
    created_at: datetime
    last_message_at: datetime
    message_count: int = 0


class ChatMessageResponse(BaseModel):
    """Persisted chat message."""

    id: int
    role: str
    content: str
    tool_calls: list[dict] = []
    tool_results: list[dict] = []
    created_at: datetime
