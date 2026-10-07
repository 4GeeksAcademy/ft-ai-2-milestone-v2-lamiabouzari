"""Milestone 10 Part 2: First-line CX WebSocket chat."""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from starlette.websockets import WebSocketDisconnect

from chat import store
from chat import stream
from chat.backoff import next_backoff_ms
from chat.bus import bus

ROOT = Path(__file__).parents[2]
QUESTION = "Where is my order?"
RETURN_QUESTION = "Where is my return?"


@pytest.fixture
def chat_db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'chat.db'}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    store.set_engine(engine)
    store.create_tables(engine)
    stream.reset()
    yield engine
    stream.reset()
    store.reset_status_changes()
    store.set_engine(None)


@pytest.fixture
def agent(monkeypatch):
    calls: list[str] = []
    checkpoints: list[str] = []
    finished: list[str] = []
    scripts: dict = {"fn": None}

    def retrieve(query, **kwargs):
        return [
            {
                "text": "The parcel is in transit.",
                "source_document": "tracking",
                "section": "status",
            }
        ]

    def iterate(question, context):
        calls.append(question)
        custom = scripts["fn"]
        if custom is not None:
            yield from custom(question, context)
            return
        yield "Tracked "
        checkpoints.append(stream.any_streamed_text())
        yield "parcel"

    monkeypatch.setattr("data.pipelines.rag.retrieve", retrieve)
    monkeypatch.setattr("data.pipelines.rag.iter_model_deltas", iterate)
    return SimpleNamespace(calls=calls, checkpoints=checkpoints, finished=finished, scripts=scripts)


def _login(client) -> str:
    response = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _open_session(client, token: str, client_id: str = "acme") -> dict:
    response = client.post(
        "/chat/sessions",
        json={"client_id": client_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _ws_url(session_id: str, token: str, thread_id: str | None = None) -> str:
    params = {"token": token}
    if thread_id is not None:
        params["thread_id"] = thread_id
    return f"/ws/chat/{session_id}?{urlencode(params)}"


def _expect_close(client, url: str, code: int) -> None:
    with pytest.raises(WebSocketDisconnect) as caught:
        with client.websocket_connect(url) as websocket:
            websocket.receive_json()
    assert caught.value.code == code


def _frames_until(websocket, event_name: str, limit: int = 30) -> list[dict]:
    frames: list[dict] = []
    for _ in range(limit):
        frame = websocket.receive_json()
        frames.append(frame)
        if frame["event"] == event_name:
            return frames
    raise AssertionError(frames)


def test_chat_session_contract(auth_client, registered_user, user_record, chat_db):
    token = _login(auth_client)
    body = _open_session(auth_client, token, "client-7")
    assert body["session_id"]
    assert body["agent_id"] == "first_line_cx"
    assert body["user_id"] == user_record["id"]
    assert body["client_id"] == "client-7"
    assert body["status"] == "active"
    assert body["created_at"]
    stored = store.get_session(body["session_id"])
    assert stored is not None
    assert stored.agent_id == "first_line_cx"
    assert stored.user_id == body["user_id"]
    assert stored.client_id == "client-7"
    assert stored.status == "active"
    assert stored.created_at is not None


def test_missing_token_is_rejected(auth_client, registered_user, chat_db, agent):
    token = _login(auth_client)
    session = _open_session(auth_client, token)
    _expect_close(auth_client, f"/ws/chat/{session['session_id']}", 4401)
    assert agent.calls == []


def test_invalid_token_is_rejected(auth_client, registered_user, chat_db, agent):
    token = _login(auth_client)
    session = _open_session(auth_client, token)
    _expect_close(auth_client, _ws_url(session["session_id"], "not-a-jwt"), 4401)
    assert agent.calls == []


def test_valid_token_can_connect(auth_client, registered_user, chat_db, agent):
    token = _login(auth_client)
    session = _open_session(auth_client, token)
    with auth_client.websocket_connect(_ws_url(session["session_id"], token)) as websocket:
        frame = websocket.receive_json()
    assert frame["event"] == "session_snapshot"
    assert agent.calls == []


def test_connection_binds_to_existing_session(auth_client, registered_user, chat_db, agent):
    token = _login(auth_client)
    session = _open_session(auth_client, token, "client-9")
    with auth_client.websocket_connect(
        _ws_url(session["session_id"], token, thread_id=session["session_id"])
    ) as websocket:
        frame = websocket.receive_json()
    data = frame["data"]
    assert data["session_id"] == session["session_id"]
    assert data["thread_id"] == session["session_id"]
    assert data["agent_id"] == "first_line_cx"
    assert data["client_id"] == "client-9"
    assert data["user_id"] == session["user_id"]


def test_unknown_session_is_rejected(auth_client, registered_user, chat_db, agent):
    token = _login(auth_client)
    _expect_close(auth_client, _ws_url(str(uuid4()), token), 4404)
    assert agent.calls == []


def test_token_chunk_and_completion_contract(auth_client, registered_user, chat_db, agent):
    token = _login(auth_client)
    session = _open_session(auth_client, token)
    session_id = session["session_id"]
    with auth_client.websocket_connect(_ws_url(session_id, token)) as websocket:
        assert websocket.receive_json()["event"] == "session_snapshot"
        websocket.send_json(
            {"event": "user_message", "data": {"session_id": session_id, "text": QUESTION}}
        )
        frames = _frames_until(websocket, "generation_completed")
    chunks = [frame for frame in frames if frame["event"] == "token_chunk"]
    assert len(chunks) >= 2
    assert [frame["event"] for frame in frames if frame["event"] == "generation_completed"]
    assert frames[-1]["event"] == "generation_completed"
    sequences = [chunk["data"]["sequence"] for chunk in chunks]
    assert sequences == list(range(1, len(sequences) + 1))
    assert chunks[0]["data"]["token"] == "Tracked "
    assert chunks[1]["data"]["token"] == "parcel"
    for chunk in chunks:
        assert chunk["event"] == "token_chunk"
        assert set(chunk["data"]) == {"session_id", "token", "sequence"}
        assert chunk["data"]["session_id"] == session_id
    completed = frames[-1]["data"]
    assert set(completed) == {"session_id", "message_id"}
    assert completed["session_id"] == session_id
    assert completed["message_id"]
    blob = str(frames)
    assert "rfp_id" not in blob
    assert "services_requested" not in blob
    assert "rfp_ticket_created" not in blob
    assert agent.checkpoints == ["Tracked "]
    assert agent.calls == [QUESTION]


def test_interrupt_cancels_the_generation_task(auth_client, registered_user, chat_db, agent):
    finished = agent.finished

    def slow(question, context):
        if "return" in question.lower():
            yield "Return "
            yield "window"
            return
        for token in ("One ", "Two ", "Three ", "Four "):
            time.sleep(0.12)
            yield token
        finished.append(question)

    agent.scripts["fn"] = slow
    token = _login(auth_client)
    session = _open_session(auth_client, token)
    session_id = session["session_id"]
    with auth_client.websocket_connect(_ws_url(session_id, token)) as websocket:
        assert websocket.receive_json()["event"] == "session_snapshot"
        websocket.send_json(
            {"event": "user_message", "data": {"session_id": session_id, "text": QUESTION}}
        )
        first = websocket.receive_json()
        assert first["event"] == "user_message"
        chunk = websocket.receive_json()
        assert chunk["event"] == "token_chunk"
        assert chunk["data"]["token"] == "One "
        task = stream.generation_task(session_id)
        old = stream.active_generation(session_id)
        assert task is not None and old is not None
        websocket.send_json(
            {
                "event": "interrupt_requested",
                "data": {"session_id": session_id, "new_input": RETURN_QUESTION},
            }
        )
        interrupted = _frames_until(websocket, "generation_interrupted")
        assert task.cancelled()
        assert finished == []
        stream.publish_token(old, "STALE-FROM-A")
        rest = _frames_until(websocket, "generation_completed")
    assert interrupted[-1]["event"] == "generation_interrupted"
    assert interrupted[-1]["data"]["status"] == "interrupted"
    assert interrupted[-1]["data"]["session_id"] == session_id
    old_message_id = interrupted[-1]["data"]["message_id"]
    later_tokens = [frame for frame in rest if frame["event"] == "token_chunk"]
    assert later_tokens
    assert all(frame["data"]["token"] != "STALE-FROM-A" for frame in later_tokens)
    assert all(frame["data"]["token"] not in {"Two ", "Three ", "Four "} for frame in later_tokens)
    assert later_tokens[0]["data"]["sequence"] == 1
    partial = store.get_message(old_message_id)
    assert partial is not None
    assert partial.status == "interrupted"
    assert partial.text == "One "
    assert "Two" not in partial.text
    new_id = rest[-1]["data"]["message_id"]
    assert new_id != old_message_id
    new_message = store.get_message(new_id)
    assert new_message is not None
    assert new_message.status == "complete"
    assert "Return" in new_message.text
    history = store.list_messages(session_id)
    assert [row.message_id for row in history if row.role == "assistant"] == [old_message_id, new_id]
    assert history[0].role == "user" and history[0].text == QUESTION
    assert any(row.text == RETURN_QUESTION and row.role == "user" for row in history)
    assert store.status_changes(session_id)[:3] == ["active", "interrupted", "active"]
    assert agent.calls[0] == QUESTION
    assert RETURN_QUESTION in agent.calls
    assert QUESTION not in finished


def test_session_can_be_closed(auth_client, registered_user, chat_db, agent):
    token = _login(auth_client)
    session = _open_session(auth_client, token)
    session_id = session["session_id"]
    with auth_client.websocket_connect(_ws_url(session_id, token)) as websocket:
        assert websocket.receive_json()["event"] == "session_snapshot"
        websocket.send_json(
            {"event": "user_message", "data": {"session_id": session_id, "text": QUESTION}}
        )
        _frames_until(websocket, "generation_completed")
        websocket.send_json({"event": "session_close", "data": {"session_id": session_id}})
        deadline = time.time() + 2
        stored = store.get_session(session_id)
        while stored is not None and stored.status != "closed" and time.time() < deadline:
            time.sleep(0.02)
            stored = store.get_session(session_id)
    stored = store.get_session(session_id)
    assert stored is not None
    assert stored.status == "closed"
    assert store.status_changes(session_id)[-1] == "closed"


def test_two_subscribers_share_one_agent_run(auth_client, registered_user, chat_db, agent):
    token = _login(auth_client)
    session = _open_session(auth_client, token)
    session_id = session["session_id"]
    url = _ws_url(session_id, token)
    with auth_client.websocket_connect(url) as first, auth_client.websocket_connect(url) as second:
        assert first.receive_json()["event"] == "session_snapshot"
        assert second.receive_json()["event"] == "session_snapshot"
        assert bus.subscriber_count(session_id) == 2
        first.send_json(
            {"event": "user_message", "data": {"session_id": session_id, "text": QUESTION}}
        )
        first_frames = _frames_until(first, "generation_completed")
        second_frames = _frames_until(second, "generation_completed")
    first_tokens = [frame["data"]["token"] for frame in first_frames if frame["event"] == "token_chunk"]
    second_tokens = [frame["data"]["token"] for frame in second_frames if frame["event"] == "token_chunk"]
    assert first_tokens == second_tokens
    assert first_tokens[:2] == ["Tracked ", "parcel"]
    assert agent.calls == [QUESTION]


def test_sessions_are_isolated(auth_client, registered_user, chat_db, agent):
    token = _login(auth_client)
    first = _open_session(auth_client, token, "client-a")
    second = _open_session(auth_client, token, "client-b")
    with (
        auth_client.websocket_connect(_ws_url(first["session_id"], token)) as chat_a,
        auth_client.websocket_connect(_ws_url(second["session_id"], token)) as chat_b,
    ):
        assert chat_a.receive_json()["event"] == "session_snapshot"
        assert chat_b.receive_json()["event"] == "session_snapshot"
        box: queue.Queue = queue.Queue()

        def listen() -> None:
            try:
                box.put(("ok", chat_b.receive_json()))
            except Exception as exc:  # noqa: BLE001 - the socket close ends the wait
                box.put(("err", exc))

        listener = threading.Thread(target=listen, daemon=True)
        listener.start()
        chat_a.send_json(
            {
                "event": "user_message",
                "data": {"session_id": first["session_id"], "text": QUESTION},
            }
        )
        _frames_until(chat_a, "generation_completed")
        try:
            outcome = box.get(timeout=0.3)
        except queue.Empty:
            outcome = ("timeout", None)
    listener.join(1)
    assert outcome[0] == "timeout"
    assert agent.calls == [QUESTION]


def test_disconnect_removes_only_that_subscriber(auth_client, registered_user, chat_db, agent):
    def paced(question, context):
        for token in ("Tracked ", "parcel"):
            time.sleep(0.15)
            yield token

    agent.scripts["fn"] = paced
    token = _login(auth_client)
    session = _open_session(auth_client, token)
    session_id = session["session_id"]
    url = _ws_url(session_id, token)
    with auth_client.websocket_connect(url) as remaining, auth_client.websocket_connect(url) as leaving:
        assert remaining.receive_json()["event"] == "session_snapshot"
        assert leaving.receive_json()["event"] == "session_snapshot"
        remaining.send_json(
            {"event": "user_message", "data": {"session_id": session_id, "text": QUESTION}}
        )
        assert remaining.receive_json()["event"] == "user_message"
        first_token = remaining.receive_json()
        assert first_token["event"] == "token_chunk"
        leaving.close()
        deadline = time.time() + 2
        while bus.subscriber_count(session_id) != 1 and time.time() < deadline:
            time.sleep(0.02)
        assert bus.subscriber_count(session_id) == 1
        rest = _frames_until(remaining, "generation_completed")
    tokens = [first_token["data"]["token"], *[frame["data"]["token"] for frame in rest if frame["event"] == "token_chunk"]]
    assert "Tracked " in tokens and "parcel" in tokens
    assert agent.calls == [QUESTION]


def test_reconnect_rehydrates_the_same_session(auth_client, registered_user, chat_db, agent):
    finished = agent.finished

    def slow(question, context):
        if "return" in question.lower():
            yield "Return "
            yield "window"
            return
        for token in ("One ", "Two ", "Three ", "Four "):
            time.sleep(0.08)
            yield token
        finished.append(question)

    token = _login(auth_client)
    session = _open_session(auth_client, token)
    session_id = session["session_id"]
    url = _ws_url(session_id, token)
    with auth_client.websocket_connect(url) as websocket:
        assert websocket.receive_json()["event"] == "session_snapshot"
        websocket.send_json(
            {"event": "user_message", "data": {"session_id": session_id, "text": QUESTION}}
        )
        _frames_until(websocket, "generation_completed")
        agent.scripts["fn"] = slow
        websocket.send_json(
            {
                "event": "user_message",
                "data": {"session_id": session_id, "text": "Where is my shipment?"},
            }
        )
        assert websocket.receive_json()["event"] == "user_message"
        assert websocket.receive_json()["data"]["token"] == "One "
        websocket.send_json(
            {
                "event": "interrupt_requested",
                "data": {"session_id": session_id, "new_input": RETURN_QUESTION},
            }
        )
        _frames_until(websocket, "generation_interrupted")
        _frames_until(websocket, "generation_completed")
    with auth_client.websocket_connect(url) as websocket:
        snapshot = websocket.receive_json()
    assert snapshot["event"] == "session_snapshot"
    assert snapshot["data"]["session_id"] == session_id
    messages = snapshot["data"]["messages"]
    assert messages
    texts = [message["text"] for message in messages]
    assert QUESTION in texts
    assert RETURN_QUESTION in texts
    assert any(message["role"] == "assistant" and message["status"] == "complete" and message["text"].startswith("Tracked") for message in messages)
    assert any(message["role"] == "assistant" and message["status"] == "interrupted" and message["text"] == "One " for message in messages)
    assert any(message["role"] == "assistant" and "Return" in message["text"] for message in messages)


def test_agent_query_stays_on_the_non_streaming_path(auth_client, registered_user, monkeypatch):
    from data.pipelines.support_agent import bind_token_stream, run_support_agent, unbind_token_stream
    from data.pipelines.support_agent import _TOKEN_SINK

    sinks_seen: list = []
    generate_calls: list[str] = []
    stream_calls: list[str] = []
    retrieved: list[str] = []

    def retrieve(query, **kwargs):
        retrieved.append(query)
        return [
            {
                "text": "The parcel is in transit.",
                "source_document": "tracking",
                "section": "status",
            }
        ]

    def generate(question, context):
        generate_calls.append(question)
        sinks_seen.append(_TOKEN_SINK.get())
        return "Shipment is in transit."

    def deltas(question, context):
        stream_calls.append(question)
        if False:
            yield ""

    from data.pipelines import support_agent as support_agent_module

    monkeypatch.setattr(support_agent_module.rag, "retrieve", retrieve)
    monkeypatch.setattr(support_agent_module.rag, "generate_answer", generate)
    monkeypatch.setattr(support_agent_module.rag, "iter_model_deltas", deltas)

    held = threading.Event()
    release = threading.Event()

    def hold_sink() -> None:
        bound = bind_token_stream(lambda _delta: None, threading.Event())
        held.set()
        assert release.wait(timeout=3)
        unbind_token_stream(bound)

    worker = threading.Thread(target=hold_sink)
    worker.start()
    assert held.wait(timeout=3)
    try:
        login = auth_client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "correct-horse"},
        )
        assert login.status_code == 200, login.text
        response = auth_client.post(
            "/agent/query",
            json={"question": QUESTION},
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        direct = run_support_agent(QUESTION)
    finally:
        release.set()
        worker.join(timeout=3)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "Shipment is in transit." in body["answer"]
    assert "Shipment is in transit." in direct["answer"]
    assert generate_calls == [QUESTION, QUESTION]
    assert stream_calls == []
    assert sinks_seen == [None, None]
    nodes = [entry["node"] for entry in direct["trace"]]
    assert nodes[:3] == ["validate_question", "retrieve_context", "generate_answer"]
    stale = bind_token_stream(lambda _delta: None, threading.Event())
    unbind_token_stream(stale)
    cleaned = run_support_agent(QUESTION)
    assert "Shipment is in transit." in cleaned["answer"]
    assert stream_calls == []
    assert _TOKEN_SINK.get() is None


def test_wrong_user_is_rejected(auth_client, registered_user, chat_db, agent):
    token = _login(auth_client)
    session = _open_session(auth_client, token)
    registered = auth_client.post(
        "/auth/register",
        json={
            "email": "bob@example.com",
            "password": "correct-horse",
            "display_name": "Bob",
        },
    )
    assert registered.status_code == 201, registered.text
    other = auth_client.post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "correct-horse"},
    )
    assert other.status_code == 200, other.text
    _expect_close(auth_client, _ws_url(session["session_id"], other.json()["access_token"]), 4403)
    assert agent.calls == []


def test_reconnect_during_active_generation(auth_client, registered_user, chat_db, agent):
    release = threading.Event()

    def paced(question, context):
        yield "One "
        assert release.wait(timeout=3)
        yield "Two "
        yield "Three "

    agent.scripts["fn"] = paced
    token = _login(auth_client)
    session = _open_session(auth_client, token)
    session_id = session["session_id"]
    url = _ws_url(session_id, token)
    with auth_client.websocket_connect(url) as websocket:
        assert websocket.receive_json()["event"] == "session_snapshot"
        websocket.send_json(
            {"event": "user_message", "data": {"session_id": session_id, "text": QUESTION}}
        )
        assert websocket.receive_json()["event"] == "user_message"
        first = websocket.receive_json()
        assert first["event"] == "token_chunk"
        assert first["data"]["token"] == "One "
    stored = store.get_message(
        next(row.message_id for row in store.list_messages(session_id) if row.role == "assistant")
    )
    assert stored is not None
    assert stored.status == "generating"
    assert stored.text == "One "
    with auth_client.websocket_connect(url) as websocket:
        snapshot = websocket.receive_json()
        assert snapshot["event"] == "session_snapshot"
        assistant = next(message for message in snapshot["data"]["messages"] if message["role"] == "assistant")
        assert assistant["text"] == "One "
        assert assistant["status"] == "generating"
        assert assistant["sequence"] == 1
        release.set()
        rest = _frames_until(websocket, "generation_completed")
    later = [frame["data"]["token"] for frame in rest if frame["event"] == "token_chunk"]
    assert later == ["Two ", "Three "]
    assert all(frame["data"]["sequence"] > 1 for frame in rest if frame["event"] == "token_chunk")
    final = store.get_message(assistant["message_id"])
    assert final is not None
    assert final.text == "One Two Three "
    assert agent.calls == [QUESTION]


def test_rejoining_viewer_does_not_start_another_run(auth_client, registered_user, chat_db, agent):
    release = threading.Event()

    def paced(question, context):
        yield "One "
        assert release.wait(timeout=3)
        yield "Two "
        yield "Three "

    agent.scripts["fn"] = paced
    token = _login(auth_client)
    session = _open_session(auth_client, token)
    session_id = session["session_id"]
    url = _ws_url(session_id, token)
    with auth_client.websocket_connect(url) as remaining:
        with auth_client.websocket_connect(url) as leaving:
            assert remaining.receive_json()["event"] == "session_snapshot"
            assert leaving.receive_json()["event"] == "session_snapshot"
            remaining.send_json(
                {"event": "user_message", "data": {"session_id": session_id, "text": QUESTION}}
            )
            assert remaining.receive_json()["event"] == "user_message"
            first = remaining.receive_json()
            assert first["data"]["token"] == "One "
            assert leaving.receive_json()["event"] == "user_message"
            assert leaving.receive_json()["data"]["token"] == "One "
        deadline = time.time() + 2
        while bus.subscriber_count(session_id) != 1 and time.time() < deadline:
            time.sleep(0.02)
        assert bus.subscriber_count(session_id) == 1
        task = stream.generation_task(session_id)
        assert task is not None and not task.done()
        with auth_client.websocket_connect(url) as rejoined:
            snapshot = rejoined.receive_json()
            assistant = next(message for message in snapshot["data"]["messages"] if message["role"] == "assistant")
            assert assistant["text"] == "One "
            assert assistant["status"] == "generating"
            assert agent.calls == [QUESTION]
            release.set()
            rejoined_rest = _frames_until(rejoined, "generation_completed")
            remaining_rest = _frames_until(remaining, "generation_completed")
    rejoined_tokens = [frame["data"]["token"] for frame in rejoined_rest if frame["event"] == "token_chunk"]
    remaining_tokens = [frame["data"]["token"] for frame in remaining_rest if frame["event"] == "token_chunk"]
    assert rejoined_tokens == ["Two ", "Three "]
    assert "Two " in remaining_tokens and "Three " in remaining_tokens
    assert agent.calls == [QUESTION]
    final = store.get_message(assistant["message_id"])
    assert final is not None
    assert final.text == "One Two Three "


def test_reconnect_backoff_is_progressive():
    assert [next_backoff_ms(attempt) for attempt in range(6)] == [1000, 2000, 4000, 8000, 16000, 30000]
    assert next_backoff_ms(10) == 30000
    source = (ROOT / "uis" / "backoffice" / "src" / "lib" / "cx-chat.ts").read_text(encoding="utf-8")
    assert "Math.min(1000 * 2 ** attempt, 30_000)" in source
