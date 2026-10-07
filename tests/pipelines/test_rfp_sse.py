"""SSE notification for a valid TrackFlow RFP. Delivery does not call a model."""

from __future__ import annotations

import json
from pathlib import Path
from queue import Empty

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from data.pipelines.rfp_approval.pipeline import start_approval
from data.pipelines.rfp_intake import extract, pipeline, store
from data.pipelines.rfp_response.pipeline import run_response
from events.bus import bus
from events.dedupe import apply_created, merge_recovered, next_backoff_ms
from events.frames import EVENT_NAME, SSE_HEADERS, format_frame
from events.rfp_notifications import maybe_publish_rfp_created
from events.stream import iter_sse
from models.rfp import RfpTicket
from tests.pipelines.test_rfp_intake import FORMAL_RFP, INFORMAL_RFP, INVALID_PITCH

ROOT = Path(__file__).parents[2]
PAYLOAD_KEYS = {
    "ticket_id",
    "rfp_id",
    "client_name",
    "client_country",
    "services_requested",
    "status",
    "created_at",
}


@pytest.fixture
def rfp_db(tmp_path):
    engine: Engine = create_engine(
        f"sqlite:///{tmp_path / 'rfp.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    store.set_engine(engine)
    store.create_tables(engine)
    bus.reset()
    yield engine
    bus.reset()
    store.set_engine(None)


def _drain(subscription, timeout: float = 0.2) -> list[dict]:
    frames = []
    while True:
        try:
            frames.append(subscription.queue.get(timeout=timeout))
        except Empty:
            return frames


def test_valid_rfp_publishes_one_analyzing_event(rfp_db, monkeypatch):
    published_while = []

    def spy(ticket_id: str):
        snapshot = store.ticket_snapshot(ticket_id)
        assert snapshot is not None
        assert snapshot["status"] == "analyzing"
        expected = extract.extract_metadata(FORMAL_RFP)
        assert snapshot["metadata"]["client_name"] == "ModaViva"
        assert snapshot["metadata"]["client_country"] == "Spain"
        assert snapshot["metadata"]["services_requested"] == expected.services_requested
        assert expected.services_requested == [
            "warehousing",
            "fulfillment",
            "reverse logistics",
            "returns processing",
        ]
        published_while.append(snapshot["status"])
        return maybe_publish_rfp_created(ticket_id)

    monkeypatch.setattr(pipeline, "maybe_publish_rfp_created", spy)
    listener = bus.subscribe()
    ticket = store.create_ticket(source_filename="modaviva.pdf", pdf_path="unused.pdf")
    assert _drain(listener, 0.05) == []
    outcome = pipeline.run_markdown(ticket.id, FORMAL_RFP)
    frames = _drain(listener)
    assert outcome["status"] == "intake_complete"
    assert published_while == ["analyzing"]
    assert len(frames) == 1
    frame = frames[0]
    assert frame["event"] == EVENT_NAME == "rfp_ticket_created"
    payload = frame["data"]
    assert set(payload) == PAYLOAD_KEYS
    finished = store.ticket_snapshot(ticket.id)
    assert finished is not None
    assert payload["ticket_id"] == ticket.id
    assert "rfp_id" in {column.name for column in RfpTicket.__table__.columns}
    stored = store.get_ticket(ticket.id)
    assert stored is not None
    assert stored.rfp_id
    assert stored.rfp_id.startswith("rfp_")
    assert finished["rfp_id"] == stored.rfp_id
    assert payload["rfp_id"] == stored.rfp_id
    assert payload["rfp_id"] != payload["ticket_id"]
    assert payload["client_name"] == "ModaViva"
    assert payload["client_country"] == "Spain"
    assert payload["services_requested"] == finished["metadata"]["services_requested"]
    assert finished["metadata"]["departments_needed"] == ["warehouse", "reverse"]
    assert payload["status"] == "analyzing"
    assert payload["created_at"] == finished["created_at"]
    wire = format_frame(frame["id"], frame["event"], payload)
    assert "event: rfp_ticket_created\n" in wire
    assert "event: message" not in wire
    decoded = json.loads(wire.split("data: ", 1)[1].strip())
    assert decoded["status"] == "analyzing"
    assert "REQUEST FOR PROPOSAL" not in wire
    assert maybe_publish_rfp_created(ticket.id) is None
    assert _drain(listener, 0.05) == []
    responded = run_response(ticket.id)
    assert responded["status"] in {"under_evaluation", "needs_human_review"}
    assert _drain(listener, 0.05) == []
    opened = start_approval(ticket.id)
    assert opened["status"] == "waiting_for_approval"
    assert _drain(listener, 0.05) == []
    assert published_while == ["analyzing"]


def test_luna_services_match_persisted_metadata_and_lastmile_routing(rfp_db):
    listener = bus.subscribe()
    ticket = store.create_ticket(source_filename="luna.pdf", pdf_path="unused.pdf")
    pipeline.run_markdown(ticket.id, INFORMAL_RFP)
    frames = _drain(listener)
    snapshot = store.ticket_snapshot(ticket.id)
    expected = extract.extract_metadata(INFORMAL_RFP)
    assert snapshot is not None
    assert len(frames) == 1
    assert frames[0]["data"]["client_name"] == "Luna Cosmetics"
    assert frames[0]["data"]["client_country"] == "United States"
    assert frames[0]["data"]["services_requested"] == snapshot["metadata"]["services_requested"]
    assert frames[0]["data"]["services_requested"] == expected.services_requested
    assert expected.services_requested == ["storage", "last-mile delivery"]
    assert snapshot["metadata"]["departments_needed"] == ["warehouse", "lastmile"]
    assert frames[0]["data"]["rfp_id"] == store.get_ticket(ticket.id).rfp_id
    assert frames[0]["data"]["rfp_id"] != frames[0]["data"]["ticket_id"]
    assert frames[0]["data"]["ticket_id"] == ticket.id


def test_each_ticket_persists_its_own_rfp_id(rfp_db):
    first = store.create_ticket(source_filename="a.pdf", pdf_path="a.pdf")
    second = store.create_ticket(source_filename="b.pdf", pdf_path="b.pdf")
    assert first.rfp_id.startswith("rfp_")
    assert second.rfp_id.startswith("rfp_")
    assert first.rfp_id != first.id
    assert second.rfp_id != second.id
    assert first.rfp_id != second.rfp_id
    assert store.get_ticket(first.id).rfp_id == first.rfp_id
    assert store.ticket_snapshot(second.id)["rfp_id"] == second.rfp_id
    assert store.ticket_snapshot(first.id)["ticket_id"] == first.id


def test_existing_rfp_tickets_table_gains_rfp_id_without_losing_rows(tmp_path):
    from sqlalchemy import text

    engine = create_engine(
        f"sqlite:///{tmp_path / 'legacy.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE rfp_tickets ("
                "id VARCHAR PRIMARY KEY, status VARCHAR NOT NULL, "
                "source_filename VARCHAR NOT NULL, pdf_path VARCHAR NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO rfp_tickets (id, status, source_filename, pdf_path) "
                "VALUES ('ticket-a', 'analyzing', 'a.pdf', 'a.pdf')"
            )
        )
    store.ensure_rfp_id_column(engine)
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT id, source_filename, status, rfp_id FROM rfp_tickets")
        ).one()
    assert row.id == "ticket-a"
    assert row.source_filename == "a.pdf"
    assert row.status == "analyzing"
    assert row.rfp_id.startswith("rfp_")
    assert row.rfp_id != row.id
    store.ensure_rfp_id_column(engine)
    with engine.connect() as connection:
        again = connection.execute(text("SELECT rfp_id FROM rfp_tickets")).one()
    assert again.rfp_id == row.rfp_id


def test_invalid_carrier_pitch_publishes_nothing(rfp_db):
    listener = bus.subscribe()
    ticket = store.create_ticket(source_filename="pitch.pdf", pdf_path="unused.pdf")
    outcome = pipeline.run_markdown(ticket.id, INVALID_PITCH)
    assert outcome["status"] == "discarded"
    assert _drain(listener, 0.05) == []
    assert store.ticket_snapshot(ticket.id)["status"] == "discarded"


def test_event_is_not_published_before_metadata_exists(rfp_db):
    listener = bus.subscribe()
    ticket = store.create_ticket(source_filename="modaviva.pdf", pdf_path="unused.pdf")
    assert maybe_publish_rfp_created(ticket.id) is None
    store.save_metadata(
        ticket.id,
        {
            "client_name": None,
            "client_country": "Spain",
            "services_requested": ["warehousing"],
            "monthly_volume": None,
            "deadline": None,
            "budget_range": None,
            "departments_needed": [],
            "currency_context": "EUR",
            "readability": {},
            "is_rfp": True,
            "document_style": "formal",
            "classification_reason": "incomplete",
        },
    )
    assert maybe_publish_rfp_created(ticket.id) is None
    assert _drain(listener, 0.05) == []
    store.save_metadata(
        ticket.id,
        {
            "client_name": "ModaViva",
            "client_country": "Spain",
            "services_requested": ["warehousing", "returns processing"],
            "monthly_volume": None,
            "deadline": None,
            "budget_range": None,
            "departments_needed": ["warehouse", "reverse"],
            "currency_context": "EUR",
            "readability": {},
            "is_rfp": True,
            "document_style": "formal",
            "classification_reason": "ready",
        },
    )
    first = maybe_publish_rfp_created(ticket.id)
    second = maybe_publish_rfp_created(ticket.id)
    assert first is not None
    assert first["status"] == "analyzing"
    assert store.ticket_snapshot(ticket.id)["status"] == "analyzing"
    assert second is None
    assert len(_drain(listener, 0.05)) == 1


def test_two_subscribers_both_receive_the_event_and_disconnect_is_removed(rfp_db):
    first = bus.subscribe()
    second = bus.subscribe()
    ticket = store.create_ticket(source_filename="modaviva.pdf", pdf_path="unused.pdf")
    pipeline.run_markdown(ticket.id, FORMAL_RFP)
    first_frames = _drain(first)
    second_frames = _drain(second)
    assert len(first_frames) == 1
    assert len(second_frames) == 1
    assert first_frames[0]["data"] == second_frames[0]["data"]
    assert first_frames[0]["data"]["ticket_id"] == ticket.id
    bus.unsubscribe(first.id)
    assert bus.subscriber_count() == 1
    delivered = bus.publish(EVENT_NAME, {"ticket_id": "other"}, "other")
    assert delivered == 1
    with pytest.raises(Empty):
        first.queue.get(timeout=0.05)
    assert second.queue.get(timeout=0.2)["id"] == "other"
    bus.unsubscribe(second.id)
    assert bus.subscriber_count() == 0


def test_keepalive_frame_and_stream_headers(rfp_db, monkeypatch):
    generator = iter_sse(0.01)
    try:
        assert next(generator) == ": keepalive\n\n"
        assert bus.subscriber_count() == 1
    finally:
        generator.close()
    assert bus.subscriber_count() == 0

    from dependencies import get_current_user
    from main import app
    from models.user import UserPublic, UserRole
    import uuid

    def one_frame(_seconds: float):
        yield ": keepalive\n\n"

    monkeypatch.setattr("routers.events.iter_sse", one_frame)
    try:
        with TestClient(app) as client:
            denied = client.get("/events/stream")
            assert denied.status_code == 401
            app.dependency_overrides[get_current_user] = lambda: UserPublic(
                id=uuid.uuid4(),
                email="sales@example.com",
                display_name="Sales",
                gravatar_url="https://www.gravatar.com/avatar/0",
                is_active=True,
                role=UserRole.user,
            )
            allowed = client.get("/events/stream")
        assert allowed.status_code == 200
        assert allowed.headers["content-type"].startswith("text/event-stream")
        assert allowed.headers["cache-control"] == "no-cache"
        assert allowed.headers["x-accel-buffering"] == "no"
        assert ": keepalive" in allowed.text
        assert SSE_HEADERS["Connection"] == "keep-alive"
        assert SSE_HEADERS["Cache-Control"] == "no-cache"
        assert SSE_HEADERS["X-Accel-Buffering"] == "no"
    finally:
        app.dependency_overrides.clear()


def test_jwt_bearer_is_accepted(auth_client, registered_user):
    denied = auth_client.get("/events/stream")
    assert denied.status_code == 401
    login = auth_client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "correct-horse"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    def one_frame(_seconds: float):
        yield ": keepalive\n\n"

    from routers import events as events_router

    original = events_router.iter_sse
    events_router.iter_sse = one_frame
    try:
        allowed = auth_client.get("/events/stream", headers={"Authorization": f"Bearer {token}"})
    finally:
        events_router.iter_sse = original
    assert allowed.status_code == 200
    assert allowed.headers["content-type"].startswith("text/event-stream")
    assert ": keepalive" in allowed.text


def test_backoff_steps_and_ticket_id_dedupe():
    assert [next_backoff_ms(attempt) for attempt in range(5)] == [1000, 2000, 4000, 8000, 16000]
    assert next_backoff_ms(10) == 30_000
    current: list[dict] = [{"ticket_id": "a", "status": "analyzing"}]
    incoming = [
        {"ticket_id": "a", "status": "intake_complete"},
        {"ticket_id": "b", "status": "analyzing"},
    ]
    recovered = merge_recovered(current, incoming)
    assert [ticket["ticket_id"] for ticket in recovered["tickets"]] == ["a", "b"]
    assert recovered["tickets"][0]["status"] == "intake_complete"
    assert [ticket["ticket_id"] for ticket in recovered["added"]] == ["b"]
    again = merge_recovered(recovered["tickets"], incoming)
    assert again["added"] == []
    assert len(again["tickets"]) == 2


def test_recovery_refetch_then_sse_does_not_duplicate(rfp_db):
    ticket = store.create_ticket(source_filename="modaviva.pdf", pdf_path="unused.pdf")
    disconnected = bus.subscribe()
    bus.unsubscribe(disconnected.id)
    pipeline.run_markdown(ticket.id, FORMAL_RFP)
    assert _drain(disconnected, 0.05) == []
    snapshot = store.ticket_snapshot(ticket.id)
    assert snapshot is not None
    recovered = merge_recovered([], [snapshot])
    assert len(recovered["added"]) == 1
    assert recovered["tickets"][0]["ticket_id"] == ticket.id
    assert recovered["tickets"][0]["status"] == "intake_complete"
    listener = bus.subscribe()
    replay = {
        "ticket_id": ticket.id,
        "rfp_id": snapshot["rfp_id"],
        "client_name": "ModaViva",
        "client_country": "Spain",
        "services_requested": ["warehousing"],
        "status": "analyzing",
        "created_at": snapshot["created_at"],
    }
    bus.publish(EVENT_NAME, replay, ticket.id)
    live = _drain(listener)
    assert len(live) == 1
    applied = apply_created(
        recovered["tickets"],
        live[0]["data"],
        {"ticket_id": ticket.id, "status": "analyzing"},
    )
    assert applied["added"] is False
    assert len(applied["tickets"]) == 1
    assert applied["tickets"][0]["status"] == "intake_complete"
    assert applied["tickets"][0]["ticket_id"] == ticket.id


def test_notification_path_does_not_call_a_model():
    files = list((ROOT / "services" / "events").glob("*.py"))
    files.append(ROOT / "services" / "routers" / "events.py")
    files.append(ROOT / "uis" / "backoffice" / "src" / "lib" / "rfp-events.ts")
    forbidden = ("openai", "litellm", "ChatOpenAI", "rfp_intake.llm", "rfp_intake.classifier", "run_support_agent")
    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        for term in forbidden:
            assert term.lower() not in text
    frontend = (ROOT / "uis" / "backoffice" / "src" / "lib" / "rfp-events.ts").read_text(encoding="utf-8")
    reader = frontend.split("async function readBody", 1)[1].split("async function loop", 1)[0]
    assert "fetchTickets" not in reader
    assert "eventsource" not in frontend.lower()
    assert "Authorization" in frontend
    assert "Bearer" in frontend
    assert 'frame.event !== "rfp_ticket_created"' in frontend
