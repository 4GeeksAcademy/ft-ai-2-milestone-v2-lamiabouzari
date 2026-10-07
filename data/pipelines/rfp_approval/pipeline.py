"""Part 3 entry and resume. One ticket, one draft per department, no Part 1 replay."""

from __future__ import annotations

from typing import Any

from data.pipelines.rfp_approval.arbitrate import cap_volume_text, detect_conflicts, promises_returns_under_48h
from data.pipelines.rfp_approval.checkpointer import (
    load_checkpoint,
    save_checkpoint,
    set_section_approval,
    set_ticket_fields,
)
from data.pipelines.rfp_approval.config import PART3_MAX_REVISIONS
from data.pipelines.rfp_approval.decisions import ApprovalError, validate_decision
from data.pipelines.rfp_approval.finalize import finalize_if_ready
from data.pipelines.rfp_approval.revise import revise_department
from data.pipelines.rfp_approval.threads import make_thread_id
from data.pipelines.rfp_approval.trace import record_trace
from data.pipelines.rfp_intake.departments import DEPARTMENTS
from data.pipelines.rfp_intake.store import ticket_snapshot
from data.pipelines.rfp_response.schemas import GenerationInput

PART3_ENTRY_STATUSES = ("under_evaluation", "needs_human_review")


class Part3NotReady(ValueError):
    """The ticket is not a persisted Part 2 handoff Part 3 can open."""


def _active_ids(snapshot: dict[str, Any]) -> list[str]:
    handoff = snapshot.get("part3_handoff") or {}
    return [str(item["department_id"]) for item in handoff.get("departments") or [] if item.get("department_id")]


def _country(snapshot: dict[str, Any]) -> str | None:
    metadata = snapshot.get("metadata") or {}
    return metadata.get("client_country")


def start_approval(ticket_id: str) -> dict[str, Any]:
    """Open one interrupt per active department. Part 2 drafts are copied, not regenerated."""
    snapshot = ticket_snapshot(ticket_id)
    if snapshot is None:
        raise KeyError(ticket_id)
    if snapshot["status"] not in PART3_ENTRY_STATUSES or not snapshot["part3_handoff_ready"]:
        raise Part3NotReady(
            "Part 3 starts from under_evaluation or needs_human_review with part3_handoff_ready."
        )
    sections = {section["department_key"]: section for section in snapshot["sections"]}
    departments = (snapshot.get("part3_handoff") or {}).get("departments") or []
    if not departments:
        raise Part3NotReady("The Part 2 handoff has no active departments.")
    opened: list[str] = []
    for item in departments:
        department_id = str(item["department_id"])
        if department_id not in DEPARTMENTS:
            raise Part3NotReady(f"{department_id} is not a TrackFlow department.")
        row = sections.get(department_id) or {}
        draft = row.get("draft_content") or item.get("draft_content") or ""
        evaluation = row.get("evaluation_results") or item.get("evaluation_result")
        if not draft or not evaluation:
            raise Part3NotReady(f"{department_id} is missing the persisted Part 2 draft or evaluation.")
        info = DEPARTMENTS[department_id]
        state = {
            "ticket_id": ticket_id,
            "department_id": department_id,
            "department_name": item.get("department_name") or info["name"],
            "owner": info["contact"],
            "thread_id": make_thread_id(ticket_id, department_id),
            "node": "approval_interrupt",
            "interrupted": True,
            "draft_content": draft,
            "evaluation_result": evaluation,
            "iteration_count": row.get("iteration_count") or item.get("iterations") or 1,
            "approval_status": "pending",
            "revision_count": 0,
            "comment": None,
            "requested_changes": None,
        }
        save_checkpoint(state)
        set_section_approval(ticket_id, department_id, "pending")
        record_trace(
            ticket_id,
            "approval_interrupt",
            "waiting",
            department=department_id,
            input_ref=state["thread_id"],
            output_ref="approval_status:pending",
        )
        opened.append(department_id)
    set_ticket_fields(ticket_id, status="waiting_for_approval")
    record_trace(
        ticket_id,
        "approval_start",
        "waiting_for_approval",
        input_ref=ticket_id,
        output_ref=",".join(opened),
    )
    refreshed = ticket_snapshot(ticket_id)
    if refreshed is None:
        raise KeyError(ticket_id)
    return refreshed


def resume_approval(ticket_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Continue one department from its checkpoint. Other departments stay as they are."""
    snapshot = ticket_snapshot(ticket_id)
    if snapshot is None:
        raise KeyError(ticket_id)
    if snapshot["status"] != "waiting_for_approval":
        raise Part3NotReady("Resume is only available while the ticket is waiting_for_approval.")
    decision = validate_decision(payload, set(_active_ids(snapshot)))
    thread_id = make_thread_id(ticket_id, decision.department)
    state = load_checkpoint(thread_id)
    if state is None or not state.get("interrupted"):
        raise ApprovalError(f"{decision.department} is not waiting at an approval interrupt.")
    record_trace(
        ticket_id,
        "approval_resume",
        decision.decision,
        department=decision.department,
        input_ref=thread_id,
        output_ref=decision.comment or decision.requested_changes or decision.decision,
    )
    if decision.decision == "approve":
        state["approval_status"] = "approved"
        state["interrupted"] = False
        state["node"] = "approved"
        state["actor"] = decision.actor
        state["comment"] = decision.comment
        save_checkpoint(state)
        set_section_approval(ticket_id, decision.department, "approved")
        record_trace(
            ticket_id,
            "approval_resume",
            "approved",
            department=decision.department,
            input_ref=thread_id,
            output_ref="approval_status:approved",
        )
        finalize_if_ready(ticket_id)
    else:
        feedback = decision.requested_changes if decision.decision == "request_changes" else decision.comment
        status = "rejected" if decision.decision == "reject" else "changes_requested"
        revise_department(
            ticket_id,
            decision.department,
            feedback or "",
            approval_status=status,
        )
    refreshed = ticket_snapshot(ticket_id)
    if refreshed is None:
        raise KeyError(ticket_id)
    return refreshed


def _mutate_for(conflict: dict[str, Any], department_id: str):
    def mutate(brief: GenerationInput) -> None:
        if conflict["conflict_id"] == "volume-vs-capacity" and department_id == "lastmile":
            capacity = int(conflict["capacity"])
            brief.monthly_volume = f"{capacity} shipments"
            brief.key_aspects = [cap_volume_text(aspect, capacity) for aspect in brief.key_aspects]
        elif conflict["conflict_id"] == "returns-sla-breach" and department_id in conflict["departments"]:
            kept = [aspect for aspect in brief.key_aspects if not promises_returns_under_48h(aspect)]
            if not any("48 hours" in aspect for aspect in kept):
                kept.append("Returns processing will not be promised in under 48 hours.")
            brief.key_aspects = kept
        elif conflict["conflict_id"] == "currency-mismatch" and department_id in conflict["departments"]:
            required = conflict.get("required_currency")
            if required in {"USD", "EUR"}:
                brief.currency_context = required

    return mutate


def apply_arbitration(ticket_id: str) -> dict[str, Any]:
    """Detect structured conflicts and route only the offending departments."""
    snapshot = ticket_snapshot(ticket_id)
    if snapshot is None:
        raise KeyError(ticket_id)
    if snapshot["status"] != "waiting_for_approval":
        raise Part3NotReady("Arbitration runs while the ticket is waiting_for_approval.")
    approvals = {item["department_id"]: item for item in snapshot.get("approvals") or []}
    sections = [
        {"department_id": department_id, "draft_content": approvals[department_id]["draft_content"]}
        for department_id in _active_ids(snapshot)
        if department_id in approvals
    ]
    conflicts = detect_conflicts(sections, _country(snapshot))
    record_trace(
        ticket_id,
        "arbitration",
        "detected",
        input_ref="structured-state",
        output_ref=",".join(item["conflict_id"] for item in conflicts) or "none",
    )
    if not conflicts:
        set_ticket_fields(ticket_id, open_conflicts=[])
        return {"conflicts": [], "routed": [], "limited": False}
    if int(snapshot.get("arbitration_iterations") or 0) >= PART3_MAX_REVISIONS:
        set_ticket_fields(ticket_id, open_conflicts=conflicts)
        record_trace(
            ticket_id,
            "arbitration",
            "revision_limit",
            input_ref="structured-state",
            output_ref="final_document_blocked",
        )
        return {"conflicts": conflicts, "routed": [], "limited": True}
    set_ticket_fields(
        ticket_id,
        arbitration_iterations=int(snapshot.get("arbitration_iterations") or 0) + 1,
        open_conflicts=conflicts,
    )
    routed: list[str] = []
    for conflict in conflicts:
        targets = [item for item in conflict["next"].split(":", 1)[1].split(",") if item]
        for department_id in targets:
            if department_id in routed:
                continue
            revise_department(
                ticket_id,
                department_id,
                str(conflict["resolution_rule"]),
                approval_status="changes_requested",
                mutate_brief=_mutate_for(conflict, department_id),
            )
            routed.append(department_id)
    refreshed = ticket_snapshot(ticket_id)
    if refreshed is None:
        raise KeyError(ticket_id)
    remaining_sections = [
        {"department_id": item["department_id"], "draft_content": item["draft_content"]}
        for item in refreshed.get("approvals") or []
    ]
    remaining = detect_conflicts(remaining_sections, _country(refreshed))
    set_ticket_fields(ticket_id, open_conflicts=remaining)
    record_trace(
        ticket_id,
        "arbitration",
        "routed",
        input_ref="structured-state",
        output_ref=",".join(routed),
    )
    return {"conflicts": conflicts, "routed": routed, "limited": False}
