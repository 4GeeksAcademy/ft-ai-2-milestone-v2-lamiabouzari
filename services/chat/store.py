"""ChatSession and ChatMessage persistence on the inventory SQL engine."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

from models.chat import AGENT_ID, ChatMessage, ChatSession

_engine: Engine | None = None
_status_lock = threading.Lock()
_status_changes: dict[str, list[str]] = {}


def set_engine(engine: Engine | None) -> None:
    """Point chat persistence at a test engine. None uses the app engine."""
    global _engine
    _engine = engine


def get_engine() -> Engine:
    if _engine is not None:
        return _engine
    from database import get_inventory_engine

    return get_inventory_engine()


def create_tables(engine: Engine | None = None) -> None:
    target = engine or get_engine()
    SQLModel.metadata.create_all(
        target,
        tables=[ChatSession.__table__, ChatMessage.__table__],
    )


def reset_status_changes() -> None:
    with _status_lock:
        _status_changes.clear()


def status_changes(session_id: str) -> list[str]:
    with _status_lock:
        return list(_status_changes.get(session_id, []))


def create_session(user_id: str, client_id: str) -> ChatSession:
    row = ChatSession(
        session_id=str(uuid.uuid4()),
        agent_id=AGENT_ID,
        user_id=user_id,
        client_id=client_id,
        status="active",
        created_at=datetime.now(UTC),
    )
    with Session(get_engine(), expire_on_commit=False) as db:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


def get_session(session_id: str) -> ChatSession | None:
    with Session(get_engine(), expire_on_commit=False) as db:
        return db.get(ChatSession, session_id)


def set_status(session_id: str, status: str) -> None:
    with Session(get_engine(), expire_on_commit=False) as db:
        row = db.get(ChatSession, session_id)
        if row is None:
            return
        row.status = status
        db.add(row)
        db.commit()
    with _status_lock:
        _status_changes.setdefault(session_id, []).append(status)


def add_message(session_id: str, role: str, text: str, status: str) -> ChatMessage:
    with Session(get_engine(), expire_on_commit=False) as db:
        current = db.exec(select(ChatMessage).where(ChatMessage.session_id == session_id)).all()
        position = len(current)
        row = ChatMessage(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            position=position,
            role=role,
            text=text,
            status=status,
            created_at=datetime.now(UTC),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


def update_message(message_id: str, text: str, status: str) -> None:
    with Session(get_engine(), expire_on_commit=False) as db:
        row = db.get(ChatMessage, message_id)
        if row is None:
            return
        row.text = text
        row.status = status
        db.add(row)
        db.commit()


def get_message(message_id: str) -> ChatMessage | None:
    with Session(get_engine(), expire_on_commit=False) as db:
        return db.get(ChatMessage, message_id)


def list_messages(session_id: str) -> list[ChatMessage]:
    with Session(get_engine(), expire_on_commit=False) as db:
        rows = db.exec(select(ChatMessage).where(ChatMessage.session_id == session_id)).all()
        return sorted(rows, key=lambda row: (row.position, row.created_at))
