"""Send one department back through its Part 2 generator and evaluators."""

from __future__ import annotations

from collections.abc import Callable

from data.pipelines.rfp_approval.checkpointer import load_checkpoint, save_checkpoint, set_section_approval
from data.pipelines.rfp_approval.config import PART3_MAX_REVISIONS
from data.pipelines.rfp_approval.threads import make_thread_id
from data.pipelines.rfp_approval.trace import record_trace
from data.pipelines.rfp_intake.store import ticket_snapshot
from data.pipelines.rfp_response.context import build_briefs
from data.pipelines.rfp_response.loop import run_department_loop
from data.pipelines.rfp_response.schemas import GenerationInput

BriefMutator = Callable[[GenerationInput], None]


def revise_department(
    ticket_id: str,
    department_id: str,
    feedback: str,
    *,
    approval_status: str,
    mutate_brief: BriefMutator | None = None,
) -> dict:
    """Revise one department. Approved siblings are not loaded or regenerated."""
    thread_id = make_thread_id(ticket_id, department_id)
    state = load_checkpoint(thread_id)
    if state is None:
        raise KeyError(thread_id)
    if int(state.get("revision_count") or 0) >= PART3_MAX_REVISIONS:
        state["approval_status"] = approval_status
        state["interrupted"] = True
        state["node"] = "revision_limit"
        state["requested_changes"] = feedback
        save_checkpoint(state)
        set_section_approval(ticket_id, department_id, approval_status)
        record_trace(
            ticket_id,
            "department_revision",
            "revision_limit",
            department=department_id,
            input_ref=thread_id,
            output_ref=f"approval_status:{approval_status}",
        )
        return {"limited": True, "department_id": department_id, "draft_content": state.get("draft_content") or ""}

    state["revision_count"] = int(state.get("revision_count") or 0) + 1
    state["approval_status"] = approval_status
    state["interrupted"] = True
    state["node"] = "revision"
    state["requested_changes"] = feedback
    save_checkpoint(state)
    set_section_approval(ticket_id, department_id, approval_status)
    record_trace(
        ticket_id,
        "department_revision",
        approval_status,
        department=department_id,
        input_ref=thread_id,
        output_ref=feedback[:180],
    )

    snapshot = ticket_snapshot(ticket_id)
    if snapshot is None:
        raise KeyError(ticket_id)
    briefs = build_briefs(snapshot.get("routing_handoff") or {}, snapshot.get("metadata"))
    brief = next((item for item in briefs if item.department_id == department_id), None)
    if brief is None:
        raise KeyError(department_id)
    brief.feedback = feedback
    if mutate_brief is not None:
        mutate_brief(brief)
    outcome = run_department_loop(ticket_id, brief)

    revised = load_checkpoint(thread_id) or state
    revised["draft_content"] = outcome.draft_content
    revised["evaluation_result"] = outcome.evaluation
    revised["iteration_count"] = outcome.evaluation.get("iterations", 1)
    revised["approval_status"] = "pending"
    revised["interrupted"] = True
    revised["node"] = "approval_interrupt"
    revised["revision_count"] = int(revised.get("revision_count") or state["revision_count"])
    save_checkpoint(revised)
    set_section_approval(ticket_id, department_id, "pending")
    record_trace(
        ticket_id,
        "department_revision",
        "returned_to_approval",
        department=department_id,
        input_ref=thread_id,
        output_ref="approval_status:pending",
    )
    return {"limited": False, "department_id": department_id, "draft_content": outcome.draft_content}
