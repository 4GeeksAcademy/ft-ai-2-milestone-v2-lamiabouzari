"""Part 3 human approval. Checkpoints are SQLite rows, not an in-memory graph."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine, select

from data.pipelines.rfp_approval.checkpointer import load_checkpoint, save_checkpoint
from data.pipelines.rfp_approval.config import PART3_MAX_REVISIONS
from data.pipelines.rfp_approval.decisions import ApprovalError
from data.pipelines.rfp_approval.finalize import finalize_if_ready, persist_document
from data.pipelines.rfp_approval.pipeline import Part3NotReady, resume_approval, start_approval
from data.pipelines.rfp_approval.threads import make_thread_id
from data.pipelines.rfp_intake import store
from data.pipelines.rfp_intake.departments import DEPARTMENTS
from data.pipelines.rfp_response.config import MAX_ITERATIONS
from data.pipelines.rfp_response.loop import run_department_loop
from models.rfp import RfpApprovalCheckpoint, RfpDepartmentSection, RfpTicket
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


def _drafts(*departments: str) -> dict[str, str]:
    return {department: CLEAN for department in departments}


def _approve(ticket_id: str, department: str) -> dict:
    return resume_approval(
        ticket_id,
        {
            "department": department,
            "decision": "approve",
            "actor": DEPARTMENTS[department]["contact"],
            "comment": "Approved as the department owner.",
            "requested_changes": None,
        },
    )


def test_part3_opens_interrupts_from_persisted_part2_drafts(rfp_db, monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("Part 3 regenerated a Part 2 draft")

    monkeypatch.setattr("data.pipelines.rfp_response.generators.generate", explode)
    monkeypatch.setattr("data.pipelines.rfp_response.loop.run_department_loop", explode)
    for status in ("under_evaluation", "needs_human_review"):
        ticket_id = seed_part2_ticket(
            departments=["warehouse", "reverse"],
            drafts=_drafts("warehouse", "reverse"),
            status=status,
        )
        before = {
            section["department_key"]: section["draft_content"]
            for section in store.ticket_snapshot(ticket_id)["sections"]
        }
        opened = start_approval(ticket_id)
        after = {section["department_key"]: section["draft_content"] for section in opened["sections"]}
        assert opened["status"] == "waiting_for_approval"
        assert after == before
        assert {item["approval_status"] for item in opened["approvals"]} == {"pending"}
        assert all(item["interrupted"] for item in opened["approvals"])
        assert all(item["node"] == "approval_interrupt" for item in opened["approvals"])
        assert opened["final_document"] is None
        for department in ("warehouse", "reverse"):
            paused = load_checkpoint(make_thread_id(ticket_id, department))
            assert paused is not None
            assert paused["thread_id"] == f"rfp-{ticket_id}:{department}"
            assert paused["node"] == "approval_interrupt"
            assert paused["interrupted"] is True
            assert paused["approval_status"] == "pending"
            assert paused["draft_content"] == before[department]


def test_invalid_and_wrong_owner_decisions_are_rejected(rfp_db):
    ticket_id = seed_part2_ticket(departments=["warehouse"], drafts=_drafts("warehouse"))
    start_approval(ticket_id)
    with pytest.raises(ApprovalError, match="decision"):
        resume_approval(
            ticket_id,
            {
                "department": "warehouse",
                "decision": "yes",
                "actor": "Ana Whitfield",
                "comment": "",
                "requested_changes": None,
            },
        )
    with pytest.raises(ApprovalError, match="cannot decide"):
        resume_approval(
            ticket_id,
            {
                "department": "warehouse",
                "decision": "approve",
                "actor": "Sofía Ramos",
                "comment": "Taking warehouse.",
                "requested_changes": None,
            },
        )
    with pytest.raises(ApprovalError, match="requested_changes"):
        resume_approval(
            ticket_id,
            {
                "department": "warehouse",
                "decision": "request_changes",
                "actor": "Ana Whitfield",
                "comment": "",
                "requested_changes": None,
            },
        )
    snapshot = store.ticket_snapshot(ticket_id)
    assert snapshot["status"] == "waiting_for_approval"
    assert snapshot["approvals"][0]["approval_status"] == "pending"
    assert snapshot["final_document"] is None


def test_resume_approves_from_checkpoint_without_restarting_the_workflow(rfp_db, monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("resume restarted the workflow")

    ticket_id = seed_part2_ticket(departments=["warehouse"], drafts=_drafts("warehouse"))
    start_approval(ticket_id)
    thread_id = make_thread_id(ticket_id, "warehouse")
    paused = load_checkpoint(thread_id)
    assert paused is not None
    assert paused["interrupted"] is True
    assert paused["approval_status"] == "pending"
    draft = paused["draft_content"]
    with Session(store.get_engine()) as session:
        section = session.exec(
            select(RfpDepartmentSection).where(RfpDepartmentSection.ticket_id == ticket_id)
        ).one()
        section.draft_content = "REPLACED SECTION MUST NOT BE APPROVED"
        session.add(section)
        session.commit()
    monkeypatch.setattr("data.pipelines.rfp_intake.pipeline.process_ticket", explode)
    monkeypatch.setattr("data.pipelines.rfp_response.pipeline.run_response", explode)
    monkeypatch.setattr("data.pipelines.rfp_approval.revise.run_department_loop", explode)
    monkeypatch.setattr("data.pipelines.rfp_intake.convert.pdf_to_markdown", explode)
    approved = _approve(ticket_id, "warehouse")
    assert approved["status"] == "done"
    assert approved["approvals"][0]["thread_id"] == thread_id
    assert approved["approvals"][0]["draft_content"] == draft
    assert "REPLACED SECTION MUST NOT BE APPROVED" not in approved["approvals"][0]["draft_content"]
    assert draft.strip() in approved["final_document"]["document_markdown"]
    assert "REPLACED SECTION MUST NOT BE APPROVED" not in approved["final_document"]["document_markdown"]
    assert approved["approvals"][0]["approval_status"] == "approved"
    assert approved["approvals"][0]["interrupted"] is False

    missing = seed_part2_ticket(departments=["warehouse"], drafts=_drafts("warehouse"))
    start_approval(missing)
    with Session(store.get_engine()) as session:
        row = session.exec(
            select(RfpApprovalCheckpoint).where(RfpApprovalCheckpoint.ticket_id == missing)
        ).one()
        session.delete(row)
        session.commit()
    with pytest.raises(ApprovalError, match="not waiting"):
        _approve(missing, "warehouse")


def test_checkpoint_survives_a_new_database_connection(tmp_path):
    path = tmp_path / "durable.sqlite"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    store.set_engine(engine)
    store.create_tables(engine)
    try:
        ticket_id = seed_part2_ticket(departments=["lastmile"], drafts=_drafts("lastmile"))
        start_approval(ticket_id)
        thread_id = make_thread_id(ticket_id, "lastmile")
        original = load_checkpoint(thread_id)
        assert original is not None
        engine.dispose()
        store.set_engine(None)
        reopened = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
        store.set_engine(reopened)
        restored = load_checkpoint(thread_id)
        assert restored is not None
        assert restored["thread_id"] == thread_id
        assert restored["draft_content"] == original["draft_content"]
        assert restored["interrupted"] is True
        assert restored["approval_status"] == "pending"
        assert restored["node"] == "approval_interrupt"
        resumed = _approve(ticket_id, "lastmile")
        assert resumed["approvals"][0]["thread_id"] == thread_id
        assert resumed["approvals"][0]["approval_status"] == "approved"
        assert resumed["approvals"][0]["draft_content"] == original["draft_content"]
        assert resumed["approvals"][0]["interrupted"] is False
        assert resumed["status"] == "done"
        assert original["draft_content"].strip() in resumed["final_document"]["document_markdown"]
        reopened.dispose()
    finally:
        store.set_engine(None)


def test_thread_ids_are_namespaced_per_ticket(rfp_db):
    first = seed_part2_ticket(departments=["warehouse"], drafts=_drafts("warehouse"))
    second = seed_part2_ticket(departments=["warehouse"], drafts=_drafts("warehouse"))
    start_approval(first)
    start_approval(second)
    first_thread = make_thread_id(first, "warehouse")
    second_thread = make_thread_id(second, "warehouse")
    assert first_thread == f"rfp-{first}:warehouse"
    assert second_thread == f"rfp-{second}:warehouse"
    assert first_thread != second_thread
    assert load_checkpoint(first_thread)["ticket_id"] == first
    assert load_checkpoint(second_thread)["ticket_id"] == second


def test_reverse_can_be_approved_while_warehouse_stays_interrupted(rfp_db):
    ticket_id = seed_part2_ticket(departments=["warehouse", "reverse"], drafts=_drafts("warehouse", "reverse"))
    start_approval(ticket_id)
    warehouse_thread = make_thread_id(ticket_id, "warehouse")
    warehouse_before = load_checkpoint(warehouse_thread)
    assert warehouse_before is not None
    assert warehouse_before["thread_id"] == f"rfp-{ticket_id}:warehouse"
    assert warehouse_before["approval_status"] == "pending"
    assert warehouse_before["interrupted"] is True
    approved = _approve(ticket_id, "reverse")
    by_id = {item["department_id"]: item for item in approved["approvals"]}
    warehouse_after = load_checkpoint(warehouse_thread)
    assert by_id["reverse"]["approval_status"] == "approved"
    assert by_id["reverse"]["interrupted"] is False
    assert by_id["warehouse"]["approval_status"] == "pending"
    assert by_id["warehouse"]["interrupted"] is True
    assert by_id["warehouse"]["node"] == "approval_interrupt"
    assert by_id["warehouse"]["thread_id"] == warehouse_thread
    assert warehouse_after == warehouse_before
    assert approved["status"] == "waiting_for_approval"
    assert approved["final_document"] is None


def test_final_document_waits_for_every_active_department(rfp_db):
    ticket_id = seed_part2_ticket(departments=["warehouse", "reverse"], drafts=_drafts("warehouse", "reverse"))
    start_approval(ticket_id)
    assert finalize_if_ready(ticket_id) is None
    waiting = _approve(ticket_id, "warehouse")
    assert waiting["status"] == "waiting_for_approval"
    assert waiting["final_document"] is None
    statuses = {item["department_id"]: item["approval_status"] for item in waiting["approvals"]}
    assert statuses["reverse"] == "pending"


def test_rejected_or_changes_requested_block_the_final_document(rfp_db, monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("revision limit still called the generator")

    monkeypatch.setattr("data.pipelines.rfp_approval.revise.run_department_loop", explode)
    ticket_id = seed_part2_ticket(departments=["warehouse", "reverse"], drafts=_drafts("warehouse", "reverse"))
    start_approval(ticket_id)
    _approve(ticket_id, "warehouse")
    limited = load_checkpoint(make_thread_id(ticket_id, "reverse"))
    limited["revision_count"] = PART3_MAX_REVISIONS
    save_checkpoint(limited)
    resume_approval(
        ticket_id,
        {
            "department": "reverse",
            "decision": "reject",
            "actor": "Sofía Ramos",
            "comment": "The returns wording is not acceptable.",
            "requested_changes": None,
        },
    )
    blocked = store.ticket_snapshot(ticket_id)
    reverse = next(item for item in blocked["approvals"] if item["department_id"] == "reverse")
    assert reverse["approval_status"] == "rejected"
    assert reverse["node"] == "revision_limit"
    assert blocked["status"] == "waiting_for_approval"
    assert blocked["final_document"] is None
    assert finalize_if_ready(ticket_id) is None

    changes = load_checkpoint(make_thread_id(ticket_id, "reverse"))
    changes["approval_status"] = "changes_requested"
    changes["interrupted"] = True
    changes["node"] = "revision_limit"
    save_checkpoint(changes)
    assert finalize_if_ready(ticket_id) is None
    assert store.ticket_snapshot(ticket_id)["final_document"] is None


def test_all_approvals_store_the_document_before_done(rfp_db, monkeypatch):
    seen: dict[str, str] = {}

    def persist(ticket_id: str, document: dict) -> int:
        seen["status_during_store"] = store.ticket_snapshot(ticket_id)["status"]
        return persist_document(ticket_id, document)

    monkeypatch.setattr("data.pipelines.rfp_approval.finalize.persist_document", persist)
    ticket_id = seed_part2_ticket(departments=["warehouse", "reverse"], drafts=_drafts("warehouse", "reverse"))
    start_approval(ticket_id)
    _approve(ticket_id, "warehouse")
    finished = _approve(ticket_id, "reverse")
    assert seen["status_during_store"] == "waiting_for_approval"
    assert finished["status"] == "done"
    assert finished["final_document"]["ticket_id"] == ticket_id
    assert "Ana Whitfield" in finished["final_document"]["document_markdown"]
    assert "Sofía Ramos" in finished["final_document"]["document_markdown"]


def test_request_changes_revises_only_that_department(rfp_db, monkeypatch):
    calls: list[str] = []

    def spy(ticket_id: str, brief):
        calls.append(brief.department_id)
        assert "Confirm dock hours before go-live." in (brief.feedback or "")
        return run_department_loop(ticket_id, brief)

    monkeypatch.setattr("data.pipelines.rfp_approval.revise.run_department_loop", spy)
    ticket_id = seed_part2_ticket(departments=["warehouse", "reverse"], drafts=_drafts("warehouse", "reverse"))
    start_approval(ticket_id)
    _approve(ticket_id, "warehouse")
    warehouse_draft = load_checkpoint(make_thread_id(ticket_id, "warehouse"))["draft_content"]
    revised = resume_approval(
        ticket_id,
        {
            "department": "reverse",
            "decision": "request_changes",
            "actor": "Sofía Ramos",
            "comment": "Please tighten the wording.",
            "requested_changes": "Confirm dock hours before go-live.",
        },
    )
    by_id = {item["department_id"]: item for item in revised["approvals"]}
    assert calls == ["reverse"]
    assert by_id["warehouse"]["approval_status"] == "approved"
    assert by_id["warehouse"]["draft_content"] == warehouse_draft
    assert by_id["reverse"]["approval_status"] == "pending"
    assert by_id["reverse"]["interrupted"] is True
    assert by_id["reverse"]["revision_count"] == 1
    assert revised["status"] == "waiting_for_approval"
    assert revised["final_document"] is None
    assert PART3_MAX_REVISIONS == MAX_ITERATIONS == 3


def test_traces_record_agent_input_output_and_timestamp(rfp_db):
    ticket_id = seed_part2_ticket(departments=["warehouse"], drafts=_drafts("warehouse"))
    start_approval(ticket_id)
    finished = _approve(ticket_id, "warehouse")
    assert finished["traces"]
    for trace in finished["traces"]:
        datetime.fromisoformat(trace["ts"])
        assert trace["agent"]
        assert trace["ticket_id"] == ticket_id
        assert trace["input_ref"]
        assert trace["output_ref"]
        assert trace["action"]
    interrupt = next(trace for trace in finished["traces"] if trace["agent"] == "approval_interrupt")
    resume = next(trace for trace in finished["traces"] if trace["action"] == "approved")
    stored = next(trace for trace in finished["traces"] if trace["agent"] == "final_synthesis")
    assert interrupt["department"] == "warehouse"
    assert interrupt["input_ref"] == f"rfp-{ticket_id}:warehouse"
    assert interrupt["output_ref"] == "approval_status:pending"
    assert interrupt["action"] == "waiting"
    assert resume["department"] == "warehouse"
    assert resume["agent"] == "approval_resume"
    assert resume["input_ref"] == f"rfp-{ticket_id}:warehouse"
    assert resume["output_ref"] == "approval_status:approved"
    assert stored["action"] == "stored"
    assert stored["input_ref"] == "approved-sections"
    assert stored["output_ref"].startswith("final_document:")


def test_part3_rejects_a_ticket_that_has_not_finished_part2(rfp_db):
    ticket_id = seed_part2_ticket(departments=["warehouse"], drafts=_drafts("warehouse"))
    with Session(store.get_engine()) as session:
        row = session.get(RfpTicket, ticket_id)
        assert row is not None
        row.status = "intake_complete"
        session.add(row)
        session.commit()
    with pytest.raises(Part3NotReady):
        start_approval(ticket_id)
