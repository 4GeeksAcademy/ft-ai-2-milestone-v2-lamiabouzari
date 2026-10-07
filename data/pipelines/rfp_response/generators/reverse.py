"""Reverse Logistics proposal generator. Sofía Ramos."""

from __future__ import annotations

from data.pipelines.rfp_response.generators.clauses import shared_body
from data.pipelines.rfp_response.schemas import GenerationInput


def generate(brief: GenerationInput) -> str:
    """Write only the reverse-logistics section. Returns stay at or above 48 hours."""
    if brief.department_id != "reverse":
        raise ValueError("The reverse generator only writes the reverse-logistics section.")
    client = brief.client_name or "the client"
    intro = "\n".join(
        [
            "## Reverse Logistics",
            "",
            f"{brief.contact} owns this Reverse Logistics section for {client}.",
            "This proposal covers returns scope only.",
            "Returns processing is not offered below the 48 hour floor.",
            "",
        ]
    )
    return intro + shared_body(brief)
