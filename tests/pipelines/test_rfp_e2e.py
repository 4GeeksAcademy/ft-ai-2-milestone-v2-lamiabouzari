"""One TrackFlow ticket from intake through approval to a stored final document."""

from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import create_engine, select, Session

from data.pipelines.rfp_approval.pipeline import resume_approval, start_approval
from data.pipelines.rfp_intake import pipeline, store
from data.pipelines.rfp_intake.departments import DEPARTMENTS
from data.pipelines.rfp_response.pipeline import run_response
from models.rfp import RfpTicket
from tests.pipelines.test_rfp_intake import FORMAL_RFP


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


def test_same_ticket_runs_from_intake_to_done(rfp_db, monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("Part 3 read the PDF again")

    ticket = store.create_ticket(source_filename="modaviva.pdf", pdf_path="missing-rfp.pdf")
    ticket_id = ticket.id
    intake = pipeline.run_markdown(ticket_id, FORMAL_RFP)
    assert intake["status"] == "intake_complete"
    responded = run_response(ticket_id)
    assert responded["ticket_id"] == ticket_id
    assert responded["status"] == "needs_human_review"
    part2_drafts = {
        section["department_key"]: section["draft_content"] for section in responded["sections"]
    }
    assert set(part2_drafts) == {"warehouse", "reverse"}
    assert all(part2_drafts.values())

    monkeypatch.setattr("data.pipelines.rfp_intake.convert.pdf_to_markdown", explode)
    monkeypatch.setattr("data.pipelines.rfp_intake.pipeline.process_ticket", explode)
    opened = start_approval(ticket_id)
    assert opened["ticket_id"] == ticket_id
    assert opened["status"] == "waiting_for_approval"
    opened_drafts = {item["department_id"]: item["draft_content"] for item in opened["approvals"]}
    assert opened_drafts == part2_drafts

    for department in ("warehouse", "reverse"):
        snapshot = resume_approval(
            ticket_id,
            {
                "department": department,
                "decision": "approve",
                "actor": DEPARTMENTS[department]["contact"],
                "comment": "Approved for the final proposal.",
                "requested_changes": None,
            },
        )
        assert snapshot["ticket_id"] == ticket_id
    assert snapshot["status"] == "done"
    assert snapshot["final_document"]["ticket_id"] == ticket_id
    for department, draft in part2_drafts.items():
        assert draft.strip() in snapshot["final_document"]["document_markdown"]
        assert DEPARTMENTS[department]["contact"] in snapshot["final_document"]["document_markdown"]
    with Session(store.get_engine()) as session:
        rows = session.exec(select(RfpTicket)).all()
    assert [row.id for row in rows] == [ticket_id]
