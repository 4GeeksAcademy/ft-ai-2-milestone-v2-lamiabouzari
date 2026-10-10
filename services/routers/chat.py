"""Chat sessions and the First-line CX WebSocket."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from chat import store
from chat.auth import authenticate_token
from chat.bus import bus
from chat.stream import close_session, handle_user_text, request_interrupt, snapshot, turn_lock
from dependencies import get_current_user
from models.chat import AGENT_ID
from models.user import UserPublic

router = APIRouter(tags=["chat"])

CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404


class ChatSessionCreate(BaseModel):
    client_id: str = Field(min_length=1, max_length=200)


class ChatSessionResponse(BaseModel):
    session_id: str
    agent_id: str
    user_id: str
    client_id: str
    status: str
    created_at: datetime


@router.post("/chat/sessions", response_model=ChatSessionResponse)
def open_chat_session(
    body: ChatSessionCreate,
    user: UserPublic = Depends(get_current_user),
) -> ChatSessionResponse:
    """Create a durable First-line CX session. The socket binds to this id."""
    row = store.create_session(user_id=str(user.id), client_id=body.client_id)
    return ChatSessionResponse(
        session_id=row.session_id,
        agent_id=AGENT_ID,
        user_id=row.user_id,
        client_id=row.client_id,
        status=row.status,
        created_at=row.created_at,
    )


async def _reject(websocket: WebSocket, code: int) -> None:
    """Accept only so the close code can be delivered. No chat frame is sent."""
    await websocket.accept()
    await websocket.close(code=code)


def _snapshot_sequence(frame: dict) -> int:
    """Sequence already included in the snapshot's live assistant text."""
    highest = 0
    for message in (frame.get("data") or {}).get("messages") or []:
        if message.get("status") == "generating":
            highest = max(highest, int(message.get("sequence") or 0))
    return highest


async def _forward(websocket: WebSocket, queue: asyncio.Queue, skip_through: int = 0) -> None:
    while True:
        frame = await queue.get()
        data = frame.get("data") or {}
        if frame.get("event") == "token_chunk" and int(data.get("sequence") or 0) <= skip_through:
            continue
        await websocket.send_json(frame)


async def _dispatch(session_id: str, payload: object) -> None:
    if not isinstance(payload, dict):
        return
    event = payload.get("event")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    if data.get("session_id") not in (None, session_id):
        return
    if event == "user_message":
        await handle_user_text(session_id, str(data.get("text") or ""))
    elif event == "interrupt_requested":
        async with turn_lock(session_id):
            await request_interrupt(session_id, str(data.get("new_input") or ""))
    elif event == "session_close":
        await close_session(session_id)


async def _receive(websocket: WebSocket, session_id: str) -> None:
    while True:
        await _dispatch(session_id, await websocket.receive_json())


@router.websocket("/ws/chat/{session_id}")
async def chat_socket(websocket: WebSocket, session_id: str) -> None:
    """Bind one subscriber to an existing First-line CX session."""
    user = authenticate_token(websocket.query_params.get("token"))
    if user is None:
        await _reject(websocket, CLOSE_UNAUTHORIZED)
        return

    # Accept as soon as the JWT is valid. Session lookup hits Postgres and must
    # not block the event loop, or the browser never leaves "Connecting…".
    await websocket.accept()
    session = await asyncio.to_thread(store.get_session, session_id)
    if session is None or session.agent_id != AGENT_ID:
        await websocket.close(code=CLOSE_NOT_FOUND)
        return
    if session.user_id != str(user.id):
        await websocket.close(code=CLOSE_FORBIDDEN)
        return

    requested_thread = websocket.query_params.get("thread_id")
    if requested_thread and requested_thread != session_id:
        await websocket.close(code=CLOSE_NOT_FOUND)
        return

    subscription_id, queue = bus.subscribe(session_id)
    sender: asyncio.Task | None = None
    receiver: asyncio.Task | None = None
    try:
        frame = await asyncio.to_thread(snapshot, session_id)
        await websocket.send_json(frame)
        sender = asyncio.create_task(_forward(websocket, queue, _snapshot_sequence(frame)))
        receiver = asyncio.create_task(_receive(websocket, session_id))
        done, pending = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in (*done, *pending):
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, Exception):
                await task
    finally:
        bus.unsubscribe(session_id, subscription_id)
