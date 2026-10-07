"""Warehouse Operations proposal generator. Ana Whitfield."""

from __future__ import annotations

from data.pipelines.rfp_response.generators.clauses import shared_body
from data.pipelines.rfp_response.schemas import GenerationInput


def generate(brief: GenerationInput) -> str:
    """Write only the warehouse section from the Part 1 handoff and prior feedback."""
    if brief.department_id != "warehouse":
        raise ValueError("The warehouse generator only writes the warehouse section.")
    client = brief.client_name or "the client"
    intro = "\n".join(
        [
            "## Warehouse Operations",
            "",
            f"{brief.contact} owns this Warehouse Operations section for {client}.",
            "This proposal covers warehouse scope only.",
            "No storage price, volume, or capacity is added beyond the intake handoff.",
            "",
        ]
    )
    return intro + shared_body(brief)
