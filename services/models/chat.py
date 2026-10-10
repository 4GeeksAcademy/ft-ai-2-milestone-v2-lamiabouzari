"""SQLModel tables for First-line CX chat. Postgres is the source of truth."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

AGENT_ID = "first_line_cx"
SESSION_STATUSES = ("active", "interrupted", "closed")
MESSAGE_STATUSES = ("generating", "complete", "interrupted", "failed")


def _now() -> datetime:
    return datetime.now(UTC)


class ChatSession(SQLModel, table=True):
    """One durable conversation with the First-line CX agent."""

    __tablename__ = "chat_sessions"

    session_id: str = Field(primary_key=True)
    agent_id: str = AGENT_ID
    user_id: str = Field(index=True)
    client_id: str
    status: str = "active"
    created_at: datetime = Field(default_factory=_now)


class ChatMessage(SQLModel, table=True):
    """One user or assistant turn. Interrupted assistant text is kept."""

    __tablename__ = "chat_messages"

    message_id: str = Field(primary_key=True)
    session_id: str = Field(foreign_key="chat_sessions.session_id", index=True)
    position: int = 0
    role: str
    text: str = ""
    status: str = "complete"
    created_at: datetime = Field(default_factory=_now)
