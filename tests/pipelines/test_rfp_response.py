"""Part 2 response generation and evaluation. No live model or Postgres required."""

from __future__ import annotations

import re
import threading
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from data.pipelines.rfp_intake import pipeline, store
from data.pipelines.rfp_intake.departments import DEPARTMENTS
from data.pipelines.rfp_response import generators as generator_registry
from data.pipelines.rfp_response import evaluate as section_evaluation
from data.pipelines.rfp_response.config import MAX_ITERATIONS
from data.pipelines.rfp_response.evaluate import evaluate_section
from data.pipelines.rfp_response.evaluators import compliance, readability, relevance
from data.pipelines.rfp_response.generators import lastmile, reverse, warehouse
from data.pipelines.rfp_response.pipeline import Part2NotReady, run_response
from data.pipelines.rfp_response.schemas import GenerationInput
from dependencies import get_current_user
from main import app
from models.user import UserPublic, UserRole
from tests.pipelines.test_rfp_intake import FORMAL_RFP

FIXTURES = Path(__file__).parent / "fixtures"
PASSING_SECTION = (FIXTURES / "trackflow_passing_section.md").read_text(encoding="utf-8")
FAILING_RETURNS_SECTION = (FIXTURES / "trackflow_failing_returns_section.md").read_text(encoding="utf-8")

SCOPE_ASPECT = "Store 12,000 apparel orders each month in Zaragoza."
SLA_ASPECT = "On-time delivery SLA: 97%."
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@pytest.fixture
def rfp_db(tmp_path):
    engine: Engine = create_engine(
        f"sqlite:///{tmp_path / 'rfp.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    store.set_engine(engine)
    store.create_tables(engine)
    yield engine
    store.set_engine(None)


def _brief(
    department: str = "warehouse",
    *,
    country: str = "Spain",
    currency: str = "EUR",
    aspects: list[str] | None = None,
    feedback: str | None = None,
) -> GenerationInput:
    info = DEPARTMENTS[department]
    return GenerationInput(
        department_id=department,
        department_name=info["name"],
        contact=info["contact"],
        client_name="ModaViva",
        client_country=country,
        currency_context=currency,
        key_aspects=aspects if aspects is not None else [SCOPE_ASPECT, SLA_ASPECT],
        open_questions=["What deadline should this department use?"],
        workstream={"needs": SCOPE_ASPECT, "questions": ["What deadline should this department use?"]},
        monthly_volume="12,000 orders",
        deadline=None,
        budget_range=None,
        feedback=feedback,
    )


def _section(department: str, aspects: list[str] | None = None) -> dict:
    info = DEPARTMENTS[department]
    return {
        "department_key": department,
        "department_name": info["name"],
        "contact": info["contact"],
        "key_aspects": aspects if aspects is not None else [SCOPE_ASPECT, SLA_ASPECT],
        "open_questions": ["What deadline should this department use?"],
    }


def _ready_ticket(
    sections: list[dict],
    *,
    country: str = "Spain",
    currency: str = "EUR",
    departments_needed: list[str] | None = None,
) -> str:
    ticket = store.create_ticket(source_filename="client.pdf", pdf_path="missing-rfp.pdf")
    store.save_metadata(
        ticket.id,
        {
            "client_name": "ModaViva",
            "client_country": country,
            "services_requested": ["warehousing"],
            "monthly_volume": "12,000 orders",
            "deadline": None,
            "budget_range": None,
            "departments_needed": departments_needed
            if departments_needed is not None
            else [section["department_key"] for section in sections],
            "currency_context": currency,
            "readability": {"word_count": 40},
            "is_rfp": True,
            "document_style": "formal",
            "classification_reason": "test handoff",
        },
    )
    store.replace_sections(
        ticket.id,
        [
            {
                "department_key": section["department_key"],
                "department_name": section["department_name"],
                "contact": section["contact"],
                "key_aspects": section["key_aspects"],
                "open_questions": section["open_questions"],
                "extract_text": "",
            }
            for section in sections
        ],
    )
    asks = [
        {
            "department_key": section["department_key"],
            "department_name": section["department_name"],
            "contact": section["contact"],
            "needs": " ".join(section["key_aspects"]),
            "questions": section["open_questions"],
        }
        for section in sections
    ]
    handoff = {
        "contract": "trackflow.rfp.intake.v1",
        "ticket_id": ticket.id,
        "ready_for_part2": True,
        "currency_context": currency,
        "synthesizer": {
            "sales_summary": f"Sales handoff for ModaViva ({country}, currency {currency}).",
            "department_asks": asks,
        },
        "sections": sections,
    }
    store.mark_intake_complete(ticket.id, currency_context=currency, handoff=handoff)
    return ticket.id


@pytest.mark.parametrize("department", ["warehouse", "lastmile", "reverse"])
def test_generator_success_uses_only_intake_facts(department):
    brief = _brief(department)
    draft = generator_registry.GENERATORS[department](brief)
    info = DEPARTMENTS[department]
    assert info["contact"] in draft
    assert info["name"] in draft
    assert "Offer currency: EUR." in draft
    assert SCOPE_ASPECT in draft
    assert "On-time delivery SLA: 97%." in draft
    assert "What deadline should this department use?" in draft
    assert "| Monthly volume tier | Discount |" in draft
    assert "under 48 hours" in draft
    for other, other_info in DEPARTMENTS.items():
        if other != department:
            assert other_info["contact"] not in draft
    source = "\n".join(brief.key_aspects + brief.open_questions + [brief.monthly_volume or ""])
    assert set(_NUMBER.findall(draft)) <= set(_NUMBER.findall(source)) | {"48"}
    assert "UPS" not in draft
    assert "FedEx" not in draft


def test_generator_adds_missing_aspect_from_feedback():
    brief = _brief("warehouse", feedback="Missing key aspect: Confirm pallet positions in Zaragoza.")
    draft = warehouse.generate(brief)
    assert "Confirm pallet positions in Zaragoza." in draft


def test_passing_fixture_evaluation_result_structure():
    result = evaluate_section(PASSING_SECTION, _brief("warehouse"), iteration=1)
    assert set(result) >= {
        "department_id",
        "readability",
        "relevance",
        "compliance",
        "overall_pass",
        "feedback_for_generator",
        "iterations",
    }
    assert result["department_id"] == "warehouse"
    assert result["iterations"] == 1
    assert result["readability"]["pass"] is True
    assert isinstance(result["readability"]["score"], int)
    assert isinstance(result["readability"]["details"], dict)
    assert result["relevance"]["pass"] is True
    assert result["relevance"]["missing_aspects"] == []
    assert result["compliance"]["pass"] is True
    assert result["compliance"]["rule_ids"] == []
    assert result["compliance"]["violations"] == []
    assert result["compliance"]["rules_checked"] == [
        "TRACKFLOW_CURRENCY",
        "TRACKFLOW_DELIVERY_SLA",
        "TRACKFLOW_RETURNS_MIN_48H",
        "TRACKFLOW_VOLUME_DISCOUNT_TIERS",
        "TRACKFLOW_NO_CARRIER_RATE_DISCLOSURE",
    ]
    assert result["overall_pass"] is True
    assert result["readability"]["pass"] and result["relevance"]["pass"] and result["compliance"]["pass"]


def test_evaluator_failure_returns_concrete_feedback():
    result = evaluate_section("improve this section", _brief("warehouse"), iteration=1)
    feedback = result["feedback_for_generator"]
    assert result["overall_pass"] is False
    assert result["readability"]["pass"] is False
    assert "improve this section" not in feedback.lower()
    assert "words" in feedback.lower()
    assert result["readability"]["details"]["word_count"] == 3


def test_failed_evaluation_sends_feedback_to_the_same_generator(rfp_db, monkeypatch):
    calls: list[str | None] = []
    real = warehouse.generate

    def wrapped(brief: GenerationInput) -> str:
        calls.append(brief.feedback)
        if len(calls) == 1:
            return real(brief).replace(SCOPE_ASPECT, "")
        return real(brief)

    monkeypatch.setitem(generator_registry.GENERATORS, "warehouse", wrapped)
    ticket_id = _ready_ticket([_section("warehouse")])
    snapshot = run_response(ticket_id)
    department = snapshot["part3_handoff"]["departments"][0]

    assert calls[0] is None
    assert calls[1] is not None
    assert f"Missing key aspect: {SCOPE_ASPECT}" in calls[1]
    assert "improve this section" not in calls[1].lower()
    assert len(calls) == 2
    assert department["evaluation_result"]["overall_pass"] is True
    assert department["iterations"] == 2
    assert SCOPE_ASPECT in department["draft_content"]
    assert snapshot["status"] == "under_evaluation"
    assert snapshot["part3_handoff_ready"] is True


def test_iteration_limit_and_exhaustion_keep_the_draft(rfp_db, monkeypatch):
    calls: list[int] = []

    def always_fail(brief: GenerationInput) -> str:
        calls.append(brief.iteration)
        if brief.feedback:
            assert "TRACKFLOW_RETURNS_MIN_48H" in brief.feedback
            assert "24 hours" in brief.feedback
        return "We will finish returns processing within 24 hours."

    monkeypatch.setitem(generator_registry.GENERATORS, "reverse", always_fail)
    ticket_id = _ready_ticket([_section("reverse")])
    snapshot = run_response(ticket_id)
    department = snapshot["part3_handoff"]["departments"][0]
    section = snapshot["sections"][0]

    assert MAX_ITERATIONS == 3
    assert calls == [1, 2, 3]
    assert snapshot["status"] == "needs_human_review"
    assert snapshot["status"] not in {"waiting_for_approval", "done"}
    assert department["needs_human_review"] is True
    assert department["approval_status"] == "pending"
    assert department["draft_content"] == "We will finish returns processing within 24 hours."
    assert department["evaluation_result"]["overall_pass"] is False
    assert department["evaluation_result"]["iterations"] == 3
    assert "TRACKFLOW_RETURNS_MIN_48H" in department["evaluation_result"]["compliance"]["rule_ids"]
    assert section["draft_content"] == department["draft_content"]
    assert section["evaluation_results"]["overall_pass"] is False
    assert section["needs_human_review"] is True
    assert snapshot["part3_handoff_ready"] is True
    assert snapshot["routing_handoff"]["contract"] == "trackflow.rfp.intake.v1"


def test_returns_under_48_hours_fails_trackflow_rule():
    brief = _brief(
        "reverse",
        aspects=["Process apparel returns for ModaViva in Zaragoza.", SLA_ASPECT],
    )
    result = evaluate_section(FAILING_RETURNS_SECTION, brief, iteration=1)
    assert result["readability"]["pass"] is True
    assert result["relevance"]["pass"] is True
    assert result["compliance"]["pass"] is False
    assert result["overall_pass"] is False
    assert "TRACKFLOW_RETURNS_MIN_48H" in result["compliance"]["rule_ids"]
    messages = " ".join(item["message"] for item in result["compliance"]["violations"])
    assert "24 hours" in messages
    assert "improve this section" not in result["feedback_for_generator"].lower()


def test_wrong_currency_for_client_country_fails_compliance():
    united_states = evaluate_section(PASSING_SECTION, _brief("warehouse", country="United States", currency="USD"), 1)
    assert united_states["compliance"]["pass"] is False
    assert "TRACKFLOW_CURRENCY" in united_states["compliance"]["rule_ids"]
    spain = evaluate_section(
        PASSING_SECTION.replace("Offer currency: EUR.", "Offer currency: USD."),
        _brief("warehouse", country="Spain", currency="EUR"),
        1,
    )
    assert spain["compliance"]["pass"] is False
    assert "TRACKFLOW_CURRENCY" in spain["compliance"]["rule_ids"]


def test_active_departments_come_from_part1_handoff(rfp_db, monkeypatch):
    called: list[str] = []
    originals = dict(generator_registry.GENERATORS)

    def spy(department: str):
        def wrapped(brief: GenerationInput) -> str:
            called.append(department)
            return originals[department](brief)

        return wrapped

    for department in originals:
        monkeypatch.setitem(generator_registry.GENERATORS, department, spy(department))
    ticket_id = _ready_ticket(
        [_section("warehouse")],
        departments_needed=["warehouse", "lastmile", "reverse"],
    )
    snapshot = run_response(ticket_id)
    assert called == ["warehouse"]
    assert [item["department_id"] for item in snapshot["part3_handoff"]["departments"]] == ["warehouse"]
    assert snapshot["status"] == "under_evaluation"
    assert snapshot["part3_handoff"]["departments"][0]["evaluation_result"]["overall_pass"] is True
    assert snapshot["part3_handoff"]["departments"][0]["approval_status"] == "pending"


def test_part2_does_not_reparse_the_pdf(rfp_db, monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("Part 2 re-parsed the PDF")

    monkeypatch.setattr("data.pipelines.rfp_intake.convert.pdf_to_markdown", explode)
    monkeypatch.setattr("data.pipelines.rfp_intake.pipeline.pdf_to_markdown", explode)
    ticket_id = _ready_ticket([_section("lastmile"), _section("reverse")])
    snapshot = run_response(ticket_id)
    assert snapshot["routing_handoff"]["contract"] == "trackflow.rfp.intake.v1"
    assert [item["department_id"] for item in snapshot["part3_handoff"]["departments"]] == [
        "lastmile",
        "reverse",
    ]
    assert all(item["draft_content"] and item["evaluation_result"] for item in snapshot["part3_handoff"]["departments"])


def test_part1_handoff_drives_part2_without_a_second_intake(rfp_db, monkeypatch):
    ticket = store.create_ticket(source_filename="modaviva.pdf", pdf_path="missing-rfp.pdf")
    pipeline.run_markdown(ticket.id, FORMAL_RFP)

    def explode(*_args, **_kwargs):
        raise AssertionError("Part 2 re-parsed the PDF")

    monkeypatch.setattr("data.pipelines.rfp_intake.convert.pdf_to_markdown", explode)
    snapshot = run_response(ticket.id)
    assert snapshot["routing_handoff"]["sections"]
    assert [item["department_id"] for item in snapshot["part3_handoff"]["departments"]] == [
        "warehouse",
        "reverse",
    ]
    assert snapshot["status"] == "needs_human_review"
    assert snapshot["part3_handoff_ready"] is True
    for department in snapshot["part3_handoff"]["departments"]:
        assert department["draft_content"]
        assert department["evaluation_result"]["compliance"]["pass"] is False
        assert "TRACKFLOW_DELIVERY_SLA" in department["evaluation_result"]["compliance"]["rule_ids"]
        assert department["iterations"] == MAX_ITERATIONS
        assert department["approval_status"] == "pending"
        assert department["needs_human_review"] is True


def test_one_department_failure_keeps_the_other_section(rfp_db, monkeypatch):
    def crash(_brief: GenerationInput) -> str:
        raise RuntimeError("reverse generator crashed")

    monkeypatch.setitem(generator_registry.GENERATORS, "reverse", crash)
    ticket_id = _ready_ticket([_section("warehouse"), _section("reverse")])
    snapshot = run_response(ticket_id)
    by_id = {item["department_id"]: item for item in snapshot["part3_handoff"]["departments"]}
    assert by_id["warehouse"]["evaluation_result"]["overall_pass"] is True
    assert SCOPE_ASPECT in by_id["warehouse"]["draft_content"]
    assert by_id["reverse"]["needs_human_review"] is True
    assert "reverse generator crashed" in by_id["reverse"]["evaluation_result"]["feedback_for_generator"]
    assert snapshot["status"] == "needs_human_review"
    stored = {section["department_key"]: section for section in snapshot["sections"]}
    assert stored["warehouse"]["draft_content"]
    assert stored["reverse"]["needs_human_review"] is True


def test_evaluators_run_concurrently_and_merge_after(monkeypatch):
    """The three evaluators start independently, overlap, and merge only after they finish."""
    order: list[tuple[str, str]] = []
    lock = threading.Lock()
    originals = {
        "read": readability.evaluate,
        "relevance": relevance.evaluate,
        "compliance": compliance.evaluate,
    }

    def wrap(name: str, function):
        def inner(*args, **kwargs):
            with lock:
                order.append((name, "start"))
            time.sleep(0.2)
            outcome = function(*args, **kwargs)
            with lock:
                order.append((name, "end"))
            return outcome

        return inner

    monkeypatch.setattr(readability, "evaluate", wrap("read", originals["read"]))
    monkeypatch.setattr(relevance, "evaluate", wrap("relevance", originals["relevance"]))
    monkeypatch.setattr(compliance, "evaluate", wrap("compliance", originals["compliance"]))

    real_merge = section_evaluation.merge_evaluation

    def merge_after_evaluators(*args, **kwargs):
        with lock:
            finished = sorted(name for name, event in order if event == "end")
            order.append(("merge", "start"))
        assert finished == ["compliance", "read", "relevance"]
        return real_merge(*args, **kwargs)

    monkeypatch.setattr(section_evaluation, "merge_evaluation", merge_after_evaluators)
    result = evaluate_section(PASSING_SECTION, _brief("warehouse"), 1)

    starts = [name for name, event in order if event == "start" and name != "merge"]
    assert sorted(starts) == ["compliance", "read", "relevance"]
    first_end = next(index for index, event in enumerate(order) if event[1] == "end")
    starts_before_first_end = [name for name, event in order[:first_end] if event == "start"]
    assert len(starts_before_first_end) >= 2
    merge_at = order.index(("merge", "start"))
    end_at = [index for index, event in enumerate(order) if event[1] == "end"]
    assert len(end_at) == 3
    assert merge_at > max(end_at)
    assert result["readability"]["pass"] is True
    assert result["relevance"]["pass"] is True
    assert result["compliance"]["pass"] is True
    assert result["overall_pass"] is (
        result["readability"]["pass"] and result["relevance"]["pass"] and result["compliance"]["pass"]
    )


def test_part2_rejects_a_ticket_that_is_not_intake_complete(rfp_db):
    ticket = store.create_ticket(source_filename="pitch.pdf", pdf_path="missing-rfp.pdf")
    store.mark_discarded(ticket.id, "Not an RFP.")
    with pytest.raises(Part2NotReady):
        run_response(ticket.id)
    assert store.ticket_snapshot(ticket.id)["status"] == "discarded"


def test_response_endpoint_runs_part2_on_the_existing_api(rfp_db):
    ticket_id = _ready_ticket([_section("warehouse")])
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
            response = client.post(f"/rfp/tickets/{ticket_id}/response")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "under_evaluation"
        assert body["part3_handoff_ready"] is True
        assert body["part3_handoff"]["contract"] == "trackflow.rfp.response.v1"
        assert body["routing_handoff"]["contract"] == "trackflow.rfp.intake.v1"
    finally:
        app.dependency_overrides.clear()


def test_lastmile_and_reverse_modules_reject_other_departments():
    with pytest.raises(ValueError):
        lastmile.generate(_brief("warehouse"))
    with pytest.raises(ValueError):
        reverse.generate(_brief("lastmile"))
