"""Orchestrator agent. Chooses department workstreams and nothing else."""

from __future__ import annotations

from data.pipelines.rfp_intake.departments import DEPARTMENTS, departments_for_text
from data.pipelines.rfp_intake.schemas import OrchestratorPlan, RfpMetadataDraft, Workstream

SYSTEM_PROMPT = """You are the TrackFlow RFP orchestrator.
Choose only the departments required by the requested scope.
Allowed keys are warehouse, lastmile, and reverse.
Do not draft answers, prices, volumes, or capacity.
Use EUR when the client country is Spain and USD when it is the United States.
Return JSON for an OrchestratorPlan."""

_OBJECTIVES = {
    "warehouse": "Confirm storage, inbound, and fulfillment scope.",
    "lastmile": "Confirm last-mile delivery and carrier scope.",
    "reverse": "Confirm returns and reverse-logistics scope.",
}


def decide(metadata: RfpMetadataDraft, markdown: str) -> OrchestratorPlan:
    """Build one workstream per requested department."""
    keys = departments_for_text(markdown) or list(metadata.departments_needed)
    workstreams = [
        Workstream(
            department_key=key,  # type: ignore[arg-type]
            department_name=DEPARTMENTS[key]["name"],
            contact=DEPARTMENTS[key]["contact"],
            objective=_OBJECTIVES[key],
        )
        for key in keys
        if key in DEPARTMENTS
    ]
    currency = metadata.currency_context
    if currency not in {"EUR", "USD", "UNKNOWN"}:
        currency = "UNKNOWN"
    return OrchestratorPlan(departments=workstreams, currency_context=currency)


def plan(metadata: RfpMetadataDraft, markdown: str) -> OrchestratorPlan:
    """Run the orchestrator agent and validate its structured output."""
    from data.pipelines.rfp_intake.llm import complete

    return complete(
        "orchestrate",
        {"metadata": metadata.model_dump(), "markdown": markdown},
        OrchestratorPlan,
    )
