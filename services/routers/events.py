"""Server-sent events for the existing FastAPI app."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from dependencies import get_current_user
from events.frames import SSE_HEADERS
from events.stream import iter_sse
from models.user import UserPublic

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream")
def event_stream(_user: UserPublic = Depends(get_current_user)) -> StreamingResponse:
    """One-way dashboard stream. The caller must send Authorization: Bearer."""
    from events import frames

    return StreamingResponse(
        iter_sse(frames.KEEPALIVE_SECONDS),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
