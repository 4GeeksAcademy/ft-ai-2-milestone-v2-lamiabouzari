"""Validate a human approval decision against the TrackFlow owner of that department."""

from __future__ import annotations

from dataclasses import dataclass

from data.pipelines.rfp_intake.departments import DEPARTMENTS

DECISIONS = ("approve", "reject", "request_changes")


class ApprovalError(ValueError):
    """The human payload cannot be applied."""


@dataclass(frozen=True)
class HumanDecision:
    department: str
    decision: str
    actor: str
    comment: str
    requested_changes: str | None


def validate_decision(payload: dict, active_departments: set[str]) -> HumanDecision:
    department = str(payload.get("department") or "")
    if department not in active_departments or department not in DEPARTMENTS:
        raise ApprovalError(f"{department or 'missing department'} is not an active department on this ticket.")
    decision = str(payload.get("decision") or "")
    if decision not in DECISIONS:
        raise ApprovalError(f"decision must be one of {', '.join(DECISIONS)}.")
    owner = DEPARTMENTS[department]["contact"]
    actor = str(payload.get("actor") or "")
    if actor != owner:
        raise ApprovalError(
            f"{actor or 'missing actor'} cannot decide {department}. The owner is {owner}."
        )
    comment = str(payload.get("comment") or "").strip()
    requested = payload.get("requested_changes")
    requested_text = None if requested is None else str(requested).strip()
    if decision == "request_changes" and not requested_text:
        raise ApprovalError("requested_changes is required when decision is request_changes.")
    if decision == "reject" and not comment:
        raise ApprovalError("comment is required when decision is reject.")
    return HumanDecision(
        department=department,
        decision=decision,
        actor=actor,
        comment=comment,
        requested_changes=requested_text,
    )
