"""Part 2 entry. Starts from a Part 1 routing handoff and does not read the PDF."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from data.pipelines.rfp_intake.store import ticket_snapshot
from data.pipelines.rfp_response.context import build_briefs
from data.pipelines.rfp_response.loop import run_department_loop
from data.pipelines.rfp_response.persist import advance_status, complete_part2
from data.pipelines.rfp_response.schemas import DepartmentOutcome, GenerationInput

PART3_CONTRACT = "trackflow.rfp.response.v1"


class Part2NotReady(ValueError):
    """The ticket is not an intake_complete handoff Part 2 can consume."""


def _department_payload(brief: GenerationInput, outcome: DepartmentOutcome) -> dict[str, Any]:
    return {
        "department_id": brief.department_id,
        "department_name": brief.department_name,
        "contact": brief.contact,
        "draft_content": outcome.draft_content,
        "evaluation_result": outcome.evaluation,
        "iterations": outcome.evaluation.get("iterations", 0),
        "approval_status": "pending",
        "needs_human_review": outcome.needs_human_review,
    }


def _run_one(ticket_id: str, brief: GenerationInput) -> DepartmentOutcome:
    return run_department_loop(ticket_id, brief)


def run_response(ticket_id: str) -> dict[str, Any]:
    """Draft and evaluate every department activated by the Part 1 routing handoff."""
    snapshot = ticket_snapshot(ticket_id)
    if snapshot is None:
        raise KeyError(ticket_id)
    if snapshot["status"] != "intake_complete" or not snapshot["handoff_ready"]:
        raise Part2NotReady(
            "Part 2 starts only from a ticket with status intake_complete and handoff_ready true."
        )
    handoff = snapshot.get("routing_handoff") or {}
    if not isinstance(handoff, dict):
        raise Part2NotReady("routing_handoff is missing.")
    handoff_ticket = handoff.get("ticket_id")
    if handoff_ticket not in {None, ticket_id}:
        raise Part2NotReady("routing_handoff.ticket_id does not match this ticket.")
    briefs = build_briefs(handoff, snapshot.get("metadata"))
    if not briefs:
        raise Part2NotReady("The Part 1 routing handoff has no active departments.")

    advance_status(ticket_id, "drafting")
    outcomes: dict[str, DepartmentOutcome] = {}
    with ThreadPoolExecutor(max_workers=max(1, len(briefs))) as pool:
        futures = {pool.submit(_run_one, ticket_id, brief): brief for brief in briefs}
        for future in as_completed(futures):
            brief = futures[future]
            outcomes[brief.department_id] = future.result()

    departments = [_department_payload(brief, outcomes[brief.department_id]) for brief in briefs]
    needs_review = any(item["needs_human_review"] for item in departments)
    part3 = {
        "contract": PART3_CONTRACT,
        "ticket_id": ticket_id,
        "part1_contract": handoff.get("contract"),
        "ready_for_part3": True,
        "needs_human_review": needs_review,
        "outcome": "needs_human_review" if needs_review else "ready_for_part3",
        "departments": departments,
    }
    complete_part2(ticket_id, part3, needs_human_review=needs_review)
    final = ticket_snapshot(ticket_id)
    if final is None:
        raise KeyError(ticket_id)
    return final
