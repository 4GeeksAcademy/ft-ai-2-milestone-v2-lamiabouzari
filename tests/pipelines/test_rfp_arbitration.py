"""Fixed TrackFlow arbitration. Conflicts come from structured draft fields."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from data.pipelines.rfp_approval.arbitrate import detect_conflicts
from data.pipelines.rfp_approval.checkpointer import load_checkpoint, set_ticket_fields
from data.pipelines.rfp_approval.config import COMMERCIAL_DIRECTOR, PART3_MAX_REVISIONS
from data.pipelines.rfp_approval.finalize import persist_document
from data.pipelines.rfp_approval.pipeline import apply_arbitration, resume_approval, start_approval
from data.pipelines.rfp_approval.threads import make_thread_id
from data.pipelines.rfp_intake import store
from tests.pipelines.rfp_part3_support import seed_part2_ticket

CLEAN = (Path(__file__).parent / "fixtures" / "trackflow_passing_section.md").read_text(encoding="utf-8")


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


def test_volume_vs_capacity_routes_lastmile_to_miguel(rfp_db, monkeypatch):
    calls: list[str] = []
    from data.pipelines.rfp_response.loop import run_department_loop

    def spy(ticket_id: str, brief):
        calls.append(brief.department_id)
        assert "Cap proposal volume" in (brief.feedback or "")
        assert brief.monthly_volume.startswith("5000")
        return run_department_loop(ticket_id, brief)

    monkeypatch.setattr("data.pipelines.rfp_approval.revise.run_department_loop", spy)
    warehouse = CLEAN + "\nCommitted capacity: 5000 shipments per month.\n"
    lastmile = CLEAN + "\nAssumed monthly volume: 12000 shipments.\n"
    no_conflict = detect_conflicts(
        [
            {
                "department_id": "warehouse",
                "draft_content": "Offer currency: EUR.\nCommitted capacity: 5000 shipments per month.\n",
            },
            {
                "department_id": "lastmile",
                "draft_content": "Offer currency: EUR.\nAssumed monthly volume: 4000 shipments.\n",
            },
        ],
        "Spain",
    )
    assert [item["conflict_id"] for item in no_conflict] == []
    detected = detect_conflicts(
        [
            {
                "department_id": "warehouse",
                "draft_content": "Offer currency: EUR.\nCommitted capacity: 5000 shipments per month.\n",
            },
            {
                "department_id": "lastmile",
                "draft_content": "Offer currency: EUR.\nAssumed monthly volume: 12000 shipments.\n",
            },
        ],
        "Spain",
    )
    assert detected[0]["conflict_id"] == "volume-vs-capacity"
    assert detected[0]["departments"] == ["warehouse", "lastmile"]
    assert detected[0]["arbiter"] == "Miguel Torres"
    assert detected[0]["next"] == "request_changes:lastmile"
    assert detected[0]["capacity"] == 5000
    ticket_id = seed_part2_ticket(departments=["warehouse", "lastmile"], drafts={"warehouse": warehouse, "lastmile": lastmile})
    start_approval(ticket_id)
    warehouse_draft = load_checkpoint(make_thread_id(ticket_id, "warehouse"))["draft_content"]
    result = apply_arbitration(ticket_id)
    conflict = result["conflicts"][0]
    assert conflict["conflict_id"] == "volume-vs-capacity"
    assert conflict["departments"] == ["warehouse", "lastmile"]
    assert conflict["arbiter"] == COMMERCIAL_DIRECTOR == "Miguel Torres"
    assert "cap" in conflict["resolution_rule"].lower()
    assert conflict["next"] == "request_changes:lastmile"
    assert result["routed"] == ["lastmile"]
    assert calls == ["lastmile"]
    after = store.ticket_snapshot(ticket_id)
    by_id = {item["department_id"]: item for item in after["approvals"]}
    assert by_id["warehouse"]["draft_content"] == warehouse_draft
    assert by_id["warehouse"]["approval_status"] == "pending"
    assert by_id["lastmile"]["approval_status"] == "pending"
    assert by_id["lastmile"]["interrupted"] is True
    assert "5000" in by_id["lastmile"]["draft_content"]
    assert after["status"] == "waiting_for_approval"
    assert after["final_document"] is None


def test_returns_under_48_hours_blocks_final_synthesis(rfp_db, monkeypatch):
    def synthesizer_must_not_run(*_args, **_kwargs):
        raise AssertionError("final synthesis ran while a returns breach remained")

    monkeypatch.setattr("data.pipelines.rfp_approval.finalize.persist_document", synthesizer_must_not_run)
    breach = "We will finish returns processing within 24 hours.\n\n" + CLEAN
    safe = detect_conflicts(
        [{"department_id": "reverse", "draft_content": CLEAN}],
        "Spain",
    )
    assert [item["conflict_id"] for item in safe] == []

    detected = detect_conflicts(
        [{"department_id": "reverse", "draft_content": breach}],
        "Spain",
    )
    assert len(detected) == 1
    assert detected[0]["conflict_id"] == "returns-sla-breach"
    assert detected[0]["departments"] == ["reverse"]
    assert detected[0]["arbiter"] == "Sofía Ramos"
    assert detected[0]["next"] == "request_changes:reverse"
    assert "within 24 hours" in breach

    other = detect_conflicts(
        [{"department_id": "warehouse", "draft_content": breach}],
        "Spain",
    )
    assert other[0]["conflict_id"] == "returns-sla-breach"
    assert other[0]["departments"] == ["warehouse"]
    assert other[0]["arbiter"] == "Miguel Torres"
    assert other[0]["next"] == "request_changes:warehouse"

    blocked_id = seed_part2_ticket(departments=["reverse"], drafts={"reverse": breach})
    start_approval(blocked_id)
    paused = load_checkpoint(make_thread_id(blocked_id, "reverse"))
    assert paused["approval_status"] == "pending"
    assert "within 24 hours" in paused["draft_content"]
    still_blocked = resume_approval(
        blocked_id,
        {
            "department": "reverse",
            "decision": "approve",
            "actor": "Sofía Ramos",
            "comment": "Approving the section as written.",
            "requested_changes": None,
        },
    )
    assert still_blocked["status"] == "waiting_for_approval"
    assert still_blocked["final_document"] is None
    assert still_blocked["approvals"][0]["approval_status"] == "approved"
    assert "within 24 hours" in still_blocked["approvals"][0]["draft_content"]
    assert still_blocked["open_conflicts"][0]["conflict_id"] == "returns-sla-breach"
    assert still_blocked["open_conflicts"][0]["departments"] == ["reverse"]
    assert still_blocked["open_conflicts"][0]["arbiter"] == "Sofía Ramos"
    assert still_blocked["open_conflicts"][0]["next"] == "request_changes:reverse"

    monkeypatch.setattr("data.pipelines.rfp_approval.finalize.persist_document", persist_document)
    ticket_id = seed_part2_ticket(departments=["reverse"], drafts={"reverse": breach})
    start_approval(ticket_id)
    original = load_checkpoint(make_thread_id(ticket_id, "reverse"))["draft_content"]
    assert "within 24 hours" in original
    result = apply_arbitration(ticket_id)
    assert result["conflicts"][0]["conflict_id"] == "returns-sla-breach"
    assert result["conflicts"][0]["departments"] == ["reverse"]
    assert result["conflicts"][0]["arbiter"] == "Sofía Ramos"
    assert result["conflicts"][0]["next"] == "request_changes:reverse"
    assert result["routed"] == ["reverse"]
    snapshot = store.ticket_snapshot(ticket_id)
    assert snapshot["final_document"] is None
    assert snapshot["status"] == "waiting_for_approval"
    assert snapshot["approvals"][0]["approval_status"] == "pending"
    assert snapshot["approvals"][0]["interrupted"] is True
    assert "within 24 hours" not in snapshot["approvals"][0]["draft_content"]


def test_currency_mismatch_uses_miguel_and_corrects_the_offending_section(rfp_db):
    lastmile = CLEAN.replace("Offer currency: EUR.", "Offer currency: USD.")
    aligned = detect_conflicts(
        [
            {"department_id": "warehouse", "draft_content": CLEAN},
            {"department_id": "lastmile", "draft_content": CLEAN},
        ],
        "Spain",
    )
    assert [item["conflict_id"] for item in aligned] == []
    detected = detect_conflicts(
        [
            {"department_id": "warehouse", "draft_content": CLEAN},
            {"department_id": "lastmile", "draft_content": lastmile},
        ],
        "Spain",
    )
    currency = next(item for item in detected if item["conflict_id"] == "currency-mismatch")
    assert currency["arbiter"] == "Miguel Torres"
    assert currency["departments"] == ["lastmile"]
    assert currency["next"] == "request_changes:lastmile"
    assert "Offer currency: USD." in lastmile
    assert "Offer currency: EUR." in CLEAN

    ticket_id = seed_part2_ticket(
        departments=["warehouse", "lastmile"],
        drafts={"warehouse": CLEAN, "lastmile": lastmile},
    )
    start_approval(ticket_id)
    warehouse_draft = load_checkpoint(make_thread_id(ticket_id, "warehouse"))["draft_content"]
    result = apply_arbitration(ticket_id)
    assert result["routed"] == ["lastmile"]
    after = store.ticket_snapshot(ticket_id)
    by_id = {item["department_id"]: item for item in after["approvals"]}
    assert by_id["warehouse"]["draft_content"] == warehouse_draft
    assert "Offer currency: EUR." in by_id["lastmile"]["draft_content"]
    assert by_id["lastmile"]["approval_status"] == "pending"
    assert after["final_document"] is None


def test_arbitration_iteration_limit_blocks_another_revision(rfp_db, monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("arbitration revised past the limit")

    monkeypatch.setattr("data.pipelines.rfp_approval.revise.run_department_loop", explode)
    reverse = "We will finish returns processing within 24 hours.\n\n" + CLEAN
    ticket_id = seed_part2_ticket(departments=["reverse"], drafts={"reverse": reverse})
    start_approval(ticket_id)
    set_ticket_fields(ticket_id, arbitration_iterations=PART3_MAX_REVISIONS)
    result = apply_arbitration(ticket_id)
    assert result["limited"] is True
    assert result["routed"] == []
    assert result["conflicts"][0]["conflict_id"] == "returns-sla-breach"
    snapshot = store.ticket_snapshot(ticket_id)
    assert snapshot["final_document"] is None
    assert snapshot["status"] == "waiting_for_approval"
    assert "within 24 hours" in snapshot["approvals"][0]["draft_content"]
    assert PART3_MAX_REVISIONS == 3
