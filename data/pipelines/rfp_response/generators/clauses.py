"""Shared proposal clauses. Generators do not invent missing commercial facts."""

from __future__ import annotations

import re

from data.pipelines.rfp_intake.departments import currency_for_country
from data.pipelines.rfp_response.schemas import GenerationInput

_CARRIER = re.compile(
    r"\b(ups|fedex|fed ex|dhl|usps|correos|seur|mrw|gls|dpd|ontrac|lasership|amazon logistics)\b",
    re.IGNORECASE,
)
_MONEY = re.compile(r"(€|\$|\bEUR\b|\bUSD\b)", re.IGNORECASE)
_SLA_LINE = re.compile(r"on-time|delivery sla|\bsla\b", re.IGNORECASE)
_PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_DISCOUNT_TIER = re.compile(
    r"(\d[\d,]*)[^\n%]{0,80}(\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)


def offer_currency(brief: GenerationInput) -> str:
    """United States uses USD and Spain uses EUR. Otherwise keep the handoff currency."""
    mapped = currency_for_country(brief.client_country)
    if mapped in {"EUR", "USD"}:
        return mapped
    if brief.currency_context in {"EUR", "USD"}:
        return brief.currency_context
    return "UNKNOWN"


def _source_lines(brief: GenerationInput) -> list[str]:
    lines = list(brief.key_aspects)
    needs = str(brief.workstream.get("needs") or "")
    if needs:
        lines.append(needs)
    if brief.monthly_volume:
        lines.append(brief.monthly_volume)
    if brief.budget_range:
        lines.append(brief.budget_range)
    return lines


def sla_paragraph(brief: GenerationInput) -> str:
    """State an on-time delivery SLA percentage only when intake already stated one."""
    for blob in _source_lines(brief):
        for line in blob.splitlines():
            if _SLA_LINE.search(line) is None:
                continue
            if re.search(r"not stated|unknown|clarification", line, re.IGNORECASE):
                continue
            match = _PERCENT.search(line)
            if match:
                return f"On-time delivery SLA: {match.group(1)}%."
    return (
        "On-time delivery SLA percentage: not stated in the intake handoff. "
        "Clarification is required before a percentage can be offered."
    )


def returns_paragraph() -> str:
    return (
        "Returns processing commitment: TrackFlow will not promise returns processing in under 48 hours. "
        "A faster returns commitment is not offered."
    )


def _currency_codes(text: str) -> set[str]:
    found: set[str] = set()
    if re.search(r"\bEUR\b|€", text):
        found.add("EUR")
    if re.search(r"\bUSD\b|\$", text):
        found.add("USD")
    return found


def pricing_paragraph(brief: GenerationInput, currency: str) -> str:
    budget = (brief.budget_range or "").strip()
    if budget and _currency_codes(budget) <= {currency}:
        return f"Stated budget range from intake: {budget}."
    if budget:
        return (
            "The intake budget uses a different currency from the client country. "
            "Final client pricing is withheld until Sales confirms an amount in the offer currency."
        )
    return (
        "Final client pricing: not stated in the intake handoff. "
        "Clarification is required before a price is offered."
    )


def discount_table(brief: GenerationInput) -> str:
    """Reproduce stated discount tiers. Otherwise leave the cells as clarifications."""
    tiers: list[tuple[str, str]] = []
    for blob in _source_lines(brief):
        for line in blob.splitlines():
            if "discount" not in line.lower():
                continue
            match = _DISCOUNT_TIER.search(line)
            if match:
                tiers.append((match.group(1), f"{match.group(2)}%"))
    if not tiers:
        rows = "| Not stated in the intake handoff | Not stated. Clarification is required before a discount is offered. |"
    else:
        rows = "\n".join(f"| {volume} | {discount} |" for volume, discount in tiers)
    return (
        "| Monthly volume tier | Discount |\n"
        "| --- | --- |\n"
        f"{rows}"
    )


def _feedback_aspects(feedback: str | None) -> list[str]:
    if not feedback:
        return []
    aspects: list[str] = []
    for line in feedback.splitlines():
        if line.startswith("Missing key aspect:"):
            aspect = line.split(":", 1)[1].strip()
            if aspect and aspect not in aspects:
                aspects.append(aspect)
    return aspects


def _redact_carrier_rate(aspect: str) -> str:
    if _CARRIER.search(aspect) and _MONEY.search(aspect):
        return (
            "A negotiated carrier rate appeared in intake and is withheld. "
            "Only final pricing offered to the client may be stated."
        )
    return aspect


def scope_block(brief: GenerationInput) -> str:
    aspects = list(brief.key_aspects)
    for extra in _feedback_aspects(brief.feedback):
        if extra not in aspects:
            aspects.append(extra)
    if not aspects:
        bullets = "- No key aspects were stated for this department in the intake handoff."
    else:
        bullets = "\n".join(f"- {_redact_carrier_rate(aspect)}" for aspect in aspects)
    return f"### Scope from intake\n\n{bullets}"


def questions_block(brief: GenerationInput) -> str:
    if not brief.open_questions:
        return "### Open questions\n\nNo open questions were recorded for this department."
    bullets = "\n".join(f"- {question}" for question in brief.open_questions)
    return f"### Open questions\n\n{bullets}"


def shared_body(brief: GenerationInput) -> str:
    """Commercial block shared by every department generator."""
    currency = offer_currency(brief)
    volume = (
        f"Stated monthly volume from intake: {brief.monthly_volume}."
        if brief.monthly_volume
        else "Monthly volume: not stated in the intake handoff. Clarification is required."
    )
    deadline = (
        f"Stated deadline from intake: {brief.deadline}."
        if brief.deadline
        else "Deadline: not stated in the intake handoff. Clarification is required."
    )
    return "\n\n".join(
        [
            scope_block(brief),
            f"Offer currency: {currency}.",
            volume,
            deadline,
            sla_paragraph(brief),
            returns_paragraph(),
            "Negotiated rates with named carriers are omitted. Only final pricing offered to the client is included.",
            pricing_paragraph(brief, currency),
            "### Volume-based discount tiers\n\n" + discount_table(brief),
            questions_block(brief),
        ]
    )
