"""Classifier agent. Structured output only: valid client RFP or not."""

from __future__ import annotations

import re

from data.pipelines.rfp_intake.departments import departments_for_text
from data.pipelines.rfp_intake.schemas import Classification

SYSTEM_PROMPT = """You classify a document for TrackFlow Sales.
Return JSON with is_rfp, document_style, and reason.
A valid RFP asks TrackFlow to operate logistics for a client.
An inbound carrier rate pitch, vendor offer, or other non-RFP is invalid.
document_style is formal when the document is a request for proposal, informal when it is a valid request written as an email or note, and not_applicable when it is not an RFP.
Do not invent client facts."""

_PITCH = (
    "rate card",
    "rate pitch",
    "become your carrier",
    "inbound carrier rate",
    "sell you transportation",
    "vendor pitch",
)
_FORMAL = re.compile(r"request for proposal|\brfp\b", re.IGNORECASE)
_ASK = re.compile(
    r"request for proposal|\brfp\b|we need you|requests warehouse|please (provide|handle|operate)",
    re.IGNORECASE,
)


def decide(markdown: str) -> Classification:
    """Distinguish a TrackFlow client RFP from any other document."""
    lowered = markdown.lower()
    if any(phrase in lowered for phrase in _PITCH):
        return Classification(
            is_rfp=False,
            document_style="not_applicable",
            reason="Inbound vendor or carrier rate pitch is not a client RFP.",
        )
    asks_trackflow = _ASK.search(markdown) is not None
    has_scope = bool(departments_for_text(markdown))
    if not asks_trackflow or not has_scope:
        return Classification(
            is_rfp=False,
            document_style="not_applicable",
            reason="The document does not request TrackFlow logistics services.",
        )
    if _FORMAL.search(markdown):
        return Classification(
            is_rfp=True,
            document_style="formal",
            reason="Formal request for TrackFlow logistics services.",
        )
    return Classification(
        is_rfp=True,
        document_style="informal",
        reason="Informal client request for TrackFlow logistics services.",
    )


def classify(markdown: str) -> Classification:
    """Run the classifier agent and validate its structured output."""
    from data.pipelines.rfp_intake.llm import complete

    return complete("classify", {"markdown": markdown}, Classification)
