"""Deterministic RFP intake tests. No live model or Postgres required."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from data.pipelines.rfp_intake import (
    classifier,
    extract,
    llm,
    orchestrator,
    pipeline,
    store,
    workers,
)
from data.pipelines.rfp_intake.schemas import RfpMetadataDraft
from dependencies import get_current_user
from main import app
from models.user import UserPublic, UserRole

FORMAL_RFP = """
REQUEST FOR PROPOSAL

Client: ModaViva
Country: Spain

ModaViva requests warehouse fulfillment and reverse logistics for apparel returns in Zaragoza.
Monthly volume: 12,000 orders.
Deadline: 2026-11-30
Budget range: EUR 40,000-60,000
Services requested: warehousing and returns processing.
TrackFlow's last-mile delivery is not requested.
"""

INFORMAL_RFP = """
Hi TrackFlow team,

We're Luna Cosmetics in the United States. We need you to store our products in Los Angeles and handle last-mile delivery to customers. Roughly 8,000 parcels a month. Hoping to start before December. Budget is around USD 25,000 to 35,000.

Thanks!
"""

INVALID_PITCH = """
Dear TrackFlow procurement,

We are Iberia Freight. Please review our inbound carrier rate card.
We would like to become your carrier partner and sell you transportation rates.
Spain domestic: EUR 3.10 per parcel.
This vendor pitch is not a client request for TrackFlow services.
"""


@pytest.fixture
def rfp_db(tmp_path):
    engine: Engine = create_engine(
        f"sqlite:///{tmp_path / 'rfp.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    store.set_engine(engine)
    store.create_tables(engine)
    llm.set_backend(None)
    yield engine
    store.set_engine(None)
    llm.set_backend(None)


def test_classifier_accepts_formal_rfp():
    result = classifier.classify(FORMAL_RFP)
    assert result.is_rfp is True
    assert result.document_style == "formal"


def test_classifier_accepts_informal_rfp():
    result = classifier.classify(INFORMAL_RFP)
    assert result.is_rfp is True
    assert result.document_style == "informal"


def test_classifier_rejects_non_rfp():
    result = classifier.classify(INVALID_PITCH)
    assert result.is_rfp is False
    assert result.document_style == "not_applicable"


def test_worker_does_not_invent_missing_figures():
    metadata = RfpMetadataDraft(
        client_name="Northwind",
        client_country="Spain",
        services_requested=["warehousing"],
        currency_context="EUR",
    )
    result = workers.analyze(
        "warehouse",
        metadata,
        "Please store the apparel inventory in Zaragoza.",
    )
    combined = " ".join(result.key_aspects + result.open_questions)
    assert "Ana Whitfield" == result.contact
    assert result.department_name == "Warehouse Operations"
    assert "volume" in " ".join(result.open_questions).lower()
    assert "10000" not in combined
    assert "EUR" not in combined or "EUR" in (metadata.budget_range or "")


def test_department_routing_for_trackflow_samples():
    spain = extract.extract_metadata(FORMAL_RFP)
    spain_plan = orchestrator.plan(spain, FORMAL_RFP)
    assert [item.department_key for item in spain_plan.departments] == ["warehouse", "reverse"]
    assert spain_plan.currency_context == "EUR"
    assert spain.client_name == "ModaViva"
    assert spain.readability["word_count"] > 0

    united_states = extract.extract_metadata(INFORMAL_RFP)
    us_plan = orchestrator.plan(united_states, INFORMAL_RFP)
    assert [item.department_key for item in us_plan.departments] == ["warehouse", "lastmile"]
    assert us_plan.currency_context == "USD"
    assert united_states.client_name == "Luna Cosmetics"


def test_invalid_rfp_does_not_invoke_workers(rfp_db):
    calls: list[str] = []

    def spy(task: str, payload: dict) -> dict:
        calls.append(task)
        return llm.grounded(task, payload)

    llm.set_backend(spy)
    ticket = store.create_ticket(source_filename="pitch.pdf", pdf_path="unused.pdf")
    outcome = pipeline.run_markdown(ticket.id, INVALID_PITCH)
    snapshot = store.ticket_snapshot(ticket.id)

    assert outcome["status"] == "discarded"
    assert outcome["workers_ran"] is False
    assert calls == ["classify"]
    assert snapshot["status"] == "discarded"
    assert snapshot["sections"] == []
    assert snapshot["handoff_ready"] is False
    assert snapshot["synthesizer"] is None


def test_valid_ticket_reaches_intake_complete(rfp_db):
    ticket = store.create_ticket(source_filename="modaviva.pdf", pdf_path="unused.pdf")
    assert store.ticket_snapshot(ticket.id)["status"] == "analyzing"
    outcome = pipeline.run_markdown(ticket.id, FORMAL_RFP)
    snapshot = store.ticket_snapshot(ticket.id)

    assert outcome["status"] == "intake_complete"
    assert snapshot["status"] == "intake_complete"
    assert snapshot["currency_context"] == "EUR"
    assert snapshot["metadata"]["departments_needed"] == ["warehouse", "reverse"]
    assert snapshot["metadata"]["readability"]["flesch_reading_ease"] is not None
    assert [section["contact"] for section in snapshot["sections"]] == [
        "Ana Whitfield",
        "Sofía Ramos",
    ]
    assert "Carlos Vega" not in snapshot["synthesizer"]["sales_summary"]
    assert snapshot["handoff_ready"] is True
    assert snapshot["routing_handoff"]["contract"] == "trackflow.rfp.intake.v1"
    assert snapshot["routing_handoff"]["ticket_id"] == ticket.id
    assert snapshot["routing_handoff"]["sections"][0]["key_aspects"]
    assert snapshot["intake_failed"] is False


def test_mid_pipeline_crash_stays_pollable_without_a_new_status(rfp_db, monkeypatch):
    monkeypatch.setattr(pipeline, "pdf_to_markdown", lambda _path: FORMAL_RFP)

    def crash(*_args, **_kwargs):
        raise RuntimeError("orchestrator crashed")

    monkeypatch.setattr(pipeline, "plan", crash)
    ticket = store.create_ticket(source_filename="modaviva.pdf", pdf_path="unused.pdf")
    outcome = pipeline.process_ticket(ticket.id)
    snapshot = store.ticket_snapshot(ticket.id)

    assert outcome["intake_failed"] is True
    assert snapshot["status"] == "analyzing"
    assert snapshot["status"] not in {
        "drafting",
        "under_evaluation",
        "waiting_for_approval",
        "done",
        "intake_complete",
        "discarded",
    }
    assert snapshot["intake_failed"] is True
    assert "orchestrator crashed" in snapshot["error_message"]
    assert snapshot["handoff_ready"] is False
    assert snapshot["routing_handoff"] is None


def test_pdf_is_converted_before_any_agent(rfp_db, monkeypatch):
    order: list[str] = []

    def convert(_path):
        order.append("convert")
        return FORMAL_RFP

    real_classify = pipeline.classify

    def wrapped(markdown: str):
        order.append("classify")
        assert "REQUEST FOR PROPOSAL" in markdown
        return real_classify(markdown)

    monkeypatch.setattr(pipeline, "pdf_to_markdown", convert)
    monkeypatch.setattr(pipeline, "classify", wrapped)
    ticket = store.create_ticket(source_filename="modaviva.pdf", pdf_path="unused.pdf")
    pipeline.process_ticket(ticket.id)
    assert order[0] == "convert"
    assert "classify" in order
    assert order.index("convert") < order.index("classify")


def test_upload_returns_analyzing_then_intake_completes(rfp_db, monkeypatch, tmp_path):
    import routers.rfp as rfp_router

    monkeypatch.setattr(rfp_router, "_RAW_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "pdf_to_markdown", lambda _path: INFORMAL_RFP)
    app.dependency_overrides[get_current_user] = lambda: UserPublic(
        id=uuid.uuid4(),
        email="sales@example.com",
        display_name="Sales",
        gravatar_url="https://www.gravatar.com/avatar/0",
        is_active=True,
        role=UserRole.user,
    )
    try:
        with TestClient(app) as client:
            response = client.post(
                "/rfp/tickets",
                files={"file": ("luna.pdf", b"%PDF-1.4\n%", "application/pdf")},
            )
            assert response.status_code == 202
            body = response.json()
            assert body["status"] == "analyzing"
            snapshot = client.get(f"/rfp/tickets/{body['ticket_id']}")
            listed = client.get("/rfp/tickets")
        assert snapshot.status_code == 200
        payload = snapshot.json()
        assert payload["status"] == "intake_complete"
        assert payload["metadata"]["client_name"] == "Luna Cosmetics"
        assert payload["currency_context"] == "USD"
        assert payload["metadata"]["departments_needed"] == ["warehouse", "lastmile"]
        assert listed.status_code == 200
        assert listed.headers["cache-control"] == "no-store"
        rows = listed.json()
        assert [row["ticket_id"] for row in rows] == [body["ticket_id"]]
        assert rows[0]["status"] == "intake_complete"
        contacts = {section["department_key"]: section["contact"] for section in rows[0]["sections"]}
        assert contacts == {"warehouse": "Ana Whitfield", "lastmile": "Carlos Vega"}
    finally:
        app.dependency_overrides.clear()
