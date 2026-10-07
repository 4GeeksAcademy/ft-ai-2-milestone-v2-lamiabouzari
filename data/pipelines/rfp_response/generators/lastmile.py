"""Last Mile and Carrier Management proposal generator. Carlos Vega."""

from __future__ import annotations

from data.pipelines.rfp_response.generators.clauses import shared_body
from data.pipelines.rfp_response.schemas import GenerationInput


def generate(brief: GenerationInput) -> str:
    """Write only the last-mile section. Named carrier rates stay out of the draft."""
    if brief.department_id != "lastmile":
        raise ValueError("The last-mile generator only writes the last-mile section.")
    client = brief.client_name or "the client"
    intro = "\n".join(
        [
            "## Last Mile and Carrier Management",
            "",
            f"{brief.contact} owns this Last Mile and Carrier Management section for {client}.",
            "This proposal covers outbound delivery scope only.",
            "Carrier names and negotiated carrier rates from intake are not copied into the offer.",
            "",
        ]
    )
    return intro + shared_body(brief)
