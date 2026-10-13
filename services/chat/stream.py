"""One agent generation per session, published to chat.<session_id>."""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field

from chat import store
from chat.bus import bus
from data.pipelines import guardrails
from data.pipelines.support_agent import (
    _owned_order_ids,
    bind_token_stream,
    run_support_agent,
    unbind_token_stream,
)
from model_input import ModelInputError, normalize_model_question
from models.chat import AGENT_ID

logger = logging.getLogger(__name__)

_GENERATION_FAILED = "The support agent could not complete this request. Please try again later."

_runtime_lock = threading.Lock()


@dataclass
class Generation:
    generation_id: str
    message_id: str
    session_id: str
    cancel: threading.Event = field(default_factory=threading.Event)
    text: str = ""
    pending: str = ""
    blocked: bool = False
    owned_order_ids: frozenset[str] = field(default_factory=frozenset)
    sequence: int = 0
    task: asyncio.Task | None = None
    settled: bool = False


@dataclass
class SessionRuntime:
    lock: threading.Lock = field(default_factory=threading.Lock)
    active: Generation | None = None
    turn_lock: asyncio.Lock | None = None


_runtimes: dict[str, SessionRuntime] = {}


def runtime(session_id: str) -> SessionRuntime:
    with _runtime_lock:
        current = _runtimes.get(session_id)
        if current is None:
            current = SessionRuntime()
            _runtimes[session_id] = current
        return current


def turn_lock(session_id: str) -> asyncio.Lock:
    current = runtime(session_id)
    if current.turn_lock is None:
        current.turn_lock = asyncio.Lock()
    return current.turn_lock


def active_generation(session_id: str) -> Generation | None:
    current = runtime(session_id)
    with current.lock:
        return current.active


def generation_task(session_id: str) -> asyncio.Task | None:
    generation = active_generation(session_id)
    return None if generation is None else generation.task


def any_streamed_text() -> str:
    with _runtime_lock:
        runtimes = list(_runtimes.values())
    texts: list[str] = []
    for current in runtimes:
        with current.lock:
            if current.active is not None:
                texts.append(current.active.text)
    return texts[-1] if texts else ""


def channel_name(session_id: str) -> str:
    return f"chat.{session_id}"


def _emit_approved(generation: Generation, current: SessionRuntime, token: str) -> None:
    """Publish one already-approved chunk. Caller holds ``current.lock``."""
    if (
        not token
        or generation.cancel.is_set()
        or generation.settled
        or generation.blocked
        or current.active is not generation
    ):
        return
    generation.sequence += 1
    generation.text += token
    sequence = generation.sequence
    text = generation.text
    message_id = generation.message_id
    session_id = generation.session_id
    store.queue_message_update(message_id, text, "generating")
    bus.publish(
        session_id,
        "token_chunk",
        {"session_id": session_id, "token": token, "sequence": sequence},
    )


def publish_token(generation: Generation, token: str) -> None:
    """Publish one approved delta, or drop it when this generation is no longer current."""
    current = runtime(generation.session_id)
    with current.lock:
        _emit_approved(generation, current, token)


def accept_model_delta(generation: Generation, token: str) -> None:
    """Hold a model delta until the existing output policy allows it to leave."""
    if not token:
        return
    current = runtime(generation.session_id)
    with current.lock:
        if generation.cancel.is_set() or generation.settled or generation.blocked or current.active is not generation:
            return
        generation.owned_order_ids = _owned_order_ids()
        generation.pending += token
        candidate = generation.text + generation.pending
        boundary = guardrails.stream_release_length(candidate, owned_order_ids=generation.owned_order_ids)
        if boundary is None:
            generation.blocked = True
            generation.cancel.set()
            generation.pending = ""
            return
        released = len(generation.text)
        generation.pending = candidate[boundary:]
        if boundary > released:
            _emit_approved(generation, current, candidate[released:boundary])


def _flush_pending(generation: Generation) -> None:
    """Release a held safe tail after the model stream has ended."""
    current = runtime(generation.session_id)
    with current.lock:
        if (
            not generation.pending
            or generation.blocked
            or generation.settled
            or generation.cancel.is_set()
            or current.active is not generation
        ):
            return
        candidate = generation.text + generation.pending
        if guardrails.output_is_sensitive(candidate, owned_order_ids=generation.owned_order_ids):
            generation.blocked = True
            generation.cancel.set()
            generation.pending = ""
            return
        chunk = generation.pending
        generation.pending = ""
        _emit_approved(generation, current, chunk)


def _invoke(generation: Generation, question: str) -> dict:
    def sink(delta: str) -> None:
        if generation.cancel.is_set() or generation.blocked:
            return
        accept_model_delta(generation, delta)

    tokens = bind_token_stream(sink, generation.cancel)
    try:
        return run_support_agent(question, thread_id=generation.session_id)
    finally:
        unbind_token_stream(tokens)


def _settle_interrupted(generation: Generation) -> bool:
    current = runtime(generation.session_id)
    with current.lock:
        if generation.settled:
            return False
        generation.settled = True
        generation.cancel.set()
        if current.active is generation:
            current.active = None
        text = generation.text
        message_id = generation.message_id
        session_id = generation.session_id
    store.update_message(message_id, text, "interrupted")
    store.set_status(session_id, "interrupted")
    bus.publish(
        session_id,
        "generation_interrupted",
        {"session_id": session_id, "message_id": message_id, "status": "interrupted"},
    )
    return True


def _settle_blocked(generation: Generation) -> None:
    """Stop a turn whose model text failed the output policy.

    The durable transcript stores only the safe refusal. The forbidden text is
    not published and is not included in this event.
    """
    current = runtime(generation.session_id)
    with current.lock:
        if generation.settled:
            return
        generation.settled = True
        generation.blocked = True
        generation.cancel.set()
        generation.pending = ""
        if current.active is generation:
            current.active = None
        message_id = generation.message_id
        session_id = generation.session_id
    store.update_message(message_id, guardrails.OUTPUT_BLOCKED_MESSAGE, "failed")
    logger.info("agent_output_guardrail outcome=blocked reason=output_sensitive")
    bus.publish(
        session_id,
        "generation_failed",
        {
            "session_id": session_id,
            "message_id": message_id,
            "message": guardrails.OUTPUT_BLOCKED_MESSAGE,
        },
    )


def _settle_failed(generation: Generation) -> None:
    """Stop a generation that raised and publish a safe message the client can show."""
    current = runtime(generation.session_id)
    with current.lock:
        if generation.settled:
            return
        generation.settled = True
        generation.cancel.set()
        if current.active is generation:
            current.active = None
        message_id = generation.message_id
        session_id = generation.session_id
    store.update_message(message_id, _GENERATION_FAILED, "failed")
    bus.publish(
        session_id,
        "generation_failed",
        {"session_id": session_id, "message_id": message_id, "message": _GENERATION_FAILED},
    )


def _model_buffer(generation: Generation) -> str:
    return generation.text + generation.pending


def _settle_completed(generation: Generation, result: dict | None) -> None:
    if generation.blocked:
        _settle_blocked(generation)
        return
    final = str((result or {}).get("answer") or "")
    current = runtime(generation.session_id)
    with current.lock:
        if generation.settled:
            return
        if generation.blocked:
            blocked = True
            candidate = ""
        else:
            blocked = False
            candidate = _model_buffer(generation)
        owned = generation.owned_order_ids
    if blocked or guardrails.output_is_sensitive(candidate, owned_order_ids=owned):
        _settle_blocked(generation)
        return
    if final == guardrails.OUTPUT_BLOCKED_MESSAGE and candidate.strip() != final:
        _settle_blocked(generation)
        return
    if final and guardrails.output_is_sensitive(final, owned_order_ids=owned):
        _settle_blocked(generation)
        return
    _flush_pending(generation)
    if generation.blocked:
        _settle_blocked(generation)
        return
    with current.lock:
        if generation.settled or generation.cancel.is_set() or generation.blocked:
            return
        streamed = generation.text
    if final.startswith(streamed) and len(final) > len(streamed):
        publish_token(generation, final[len(streamed) :])
    elif not streamed and final:
        publish_token(generation, final)
    with current.lock:
        if generation.settled or generation.cancel.is_set() or generation.blocked:
            return
        generation.settled = True
        if current.active is generation:
            current.active = None
        text = generation.text
        message_id = generation.message_id
        session_id = generation.session_id
    store.update_message(message_id, text, "complete")
    bus.publish(
        session_id,
        "generation_completed",
        {"session_id": session_id, "message_id": message_id},
    )


async def _produce(generation: Generation, question: str) -> None:
    generation.task = asyncio.current_task()
    result = None
    try:
        result = await asyncio.to_thread(_invoke, generation, question)
    except asyncio.CancelledError:
        if generation.blocked:
            _settle_blocked(generation)
        else:
            _settle_interrupted(generation)
        raise
    except Exception as exc:
        logger.error(
            "support generation failed session=%s error_type=%s",
            generation.session_id,
            type(exc).__name__,
        )
        if generation.blocked:
            _settle_blocked(generation)
            return
        if generation.cancel.is_set():
            _settle_interrupted(generation)
            return
        _settle_failed(generation)
        return
    if generation.blocked:
        _settle_blocked(generation)
        return
    if generation.cancel.is_set():
        _settle_interrupted(generation)
        return
    _settle_completed(generation, result)


async def start_generation(session_id: str, text: str) -> None:
    try:
        question = normalize_model_question(text)
    except ModelInputError:
        return
    session = store.get_session(session_id)
    if session is None or session.status == "closed":
        return
    current = runtime(session_id)
    with current.lock:
        if current.active is not None and not current.active.settled:
            return
        user_message = store.add_message(session_id, "user", question, "complete")
        assistant = store.add_message(session_id, "assistant", "", "generating")
        generation = Generation(
            generation_id=str(uuid.uuid4()),
            message_id=assistant.message_id,
            session_id=session_id,
        )
        current.active = generation
        store.set_status(session_id, "active")
        bus.publish(
            session_id,
            "user_message",
            {
                "session_id": session_id,
                "message_id": user_message.message_id,
                "text": question,
            },
        )
    generation.task = asyncio.create_task(_produce(generation, question))


async def request_interrupt(session_id: str, new_input: str) -> None:
    """Cancel the live generation, then start one new turn from new_input."""
    current = runtime(session_id)
    with current.lock:
        generation = current.active
        if generation is None or generation.settled:
            generation = None
            task = None
        else:
            generation.cancel.set()
            task = generation.task
    if task is not None:
        task.cancel()
        await asyncio.wait({task})
    if generation is not None:
        _settle_interrupted(generation)
    if new_input.strip():
        await start_generation(session_id, new_input)


async def handle_user_text(session_id: str, text: str) -> None:
    async with turn_lock(session_id):
        generation = active_generation(session_id)
        if generation is not None and not generation.settled:
            await request_interrupt(session_id, text)
            return
        await start_generation(session_id, text)


async def close_session(session_id: str) -> None:
    async with turn_lock(session_id):
        await request_interrupt(session_id, "")
        store.set_status(session_id, "closed")


def snapshot(session_id: str) -> dict:
    session = store.get_session(session_id)
    if session is None:
        return {}
    current = runtime(session_id)
    with current.lock:
        active = current.active
        active_id = None
        active_text = ""
        active_sequence = 0
        if active is not None and not active.settled:
            active_id = active.message_id
            active_text = active.text
            active_sequence = active.sequence
        rows = store.list_messages(session_id)
    messages = []
    for row in rows:
        item = {
            "message_id": row.message_id,
            "role": row.role,
            "text": active_text if row.message_id == active_id else row.text,
            "status": "generating" if row.message_id == active_id else row.status,
        }
        if row.message_id == active_id:
            item["sequence"] = active_sequence
        messages.append(item)
    return {
        "event": "session_snapshot",
        "data": {
            "session_id": session.session_id,
            "agent_id": AGENT_ID,
            "user_id": session.user_id,
            "client_id": session.client_id,
            "status": session.status,
            "created_at": session.created_at.isoformat(),
            "thread_id": session.session_id,
            "messages": messages,
        },
    }


def reset() -> None:
    with _runtime_lock:
        runtimes = list(_runtimes.values())
        _runtimes.clear()
    for current in runtimes:
        with current.lock:
            generation = current.active
            task = None if generation is None else generation.task
            if generation is not None:
                generation.cancel.set()
        if task is not None and not task.done():
            task.cancel()
    bus.reset()
    store.reset_status_changes()
