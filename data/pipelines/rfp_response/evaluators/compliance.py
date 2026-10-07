"""TrackFlow compliance evaluator. Each rule has a stable id."""

from __future__ import annotations

import re

from data.pipelines.rfp_intake.departments import currency_for_country
from data.pipelines.rfp_response.schemas import GenerationInput

TRACKFLOW_CURRENCY = "TRACKFLOW_CURRENCY"
TRACKFLOW_DELIVERY_SLA = "TRACKFLOW_DELIVERY_SLA"
TRACKFLOW_RETURNS_MIN_48H = "TRACKFLOW_RETURNS_MIN_48H"
TRACKFLOW_VOLUME_DISCOUNT_TIERS = "TRACKFLOW_VOLUME_DISCOUNT_TIERS"
TRACKFLOW_NO_CARRIER_RATE_DISCLOSURE = "TRACKFLOW_NO_CARRIER_RATE_DISCLOSURE"

RULE_IDS = (
    TRACKFLOW_CURRENCY,
    TRACKFLOW_DELIVERY_SLA,
    TRACKFLOW_RETURNS_MIN_48H,
    TRACKFLOW_VOLUME_DISCOUNT_TIERS,
    TRACKFLOW_NO_CARRIER_RATE_DISCLOSURE,
)

_OFFER_CURRENCY = re.compile(r"Offer currency:\s*(USD|EUR|UNKNOWN)\b", re.IGNORECASE)
_SLA = re.compile(r"on-time delivery sla", re.IGNORECASE)
_PERCENT = re.compile(r"\d+(?:\.\d+)?\s*%")
_UNDER_48 = re.compile(
    r"\b(?:under|less than|fewer than|below|shorter than)\s+48\s*hours?\b",
    re.IGNORECASE,
)
_WITHIN_HOURS = re.compile(r"\b(?:within|in|inside)\s+(\d+)\s*hours?\b", re.IGNORECASE)
_HYPHEN_HOURS = re.compile(r"\b(\d+)\s*-\s*hour\b", re.IGNORECASE)
_FAST_RETURNS = re.compile(r"\b(same[- ]day|next[- ]day|overnight)\b", re.IGNORECASE)
_NEGATION = re.compile(
    r"\b(not|no|never|won't|wont|cannot|can't|cant|must not|will not)\b",
    re.IGNORECASE,
)
_CARRIER = re.compile(
    r"\b(ups|fedex|fed ex|dhl|usps|correos|seur|mrw|gls|dpd|ontrac|lasership|amazon logistics)\b",
    re.IGNORECASE,
)
_PRICE = re.compile(
    r"(€|\$|\bEUR\b|\bUSD\b|\d+(?:[.,]\d+)?\s*(?:eur|usd|€|\$))",
    re.IGNORECASE,
)
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}")


def _negated(window: str) -> bool:
    return _NEGATION.search(window) is not None


def _returns_nearby(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 80) : min(len(text), end + 80)].lower()
    return "return" in window


def _currency_violation(text: str, brief: GenerationInput) -> str | None:
    required = currency_for_country(brief.client_country)
    if required not in {"EUR", "USD"}:
        return None
    wrong = "EUR" if required == "USD" else "USD"
    offer = _OFFER_CURRENCY.search(text)
    if offer is None:
        return (
            f"Client country {brief.client_country} requires {required}. "
            "Add a line of the form 'Offer currency: "
            f"{required}.'"
        )
    stated = offer.group(1).upper()
    if stated != required:
        return (
            f"Client country {brief.client_country} requires {required}. "
            f"The draft states Offer currency: {stated}."
        )
    if wrong == "EUR" and re.search(r"\bEUR\b|€", text):
        return (
            f"Client country {brief.client_country} requires USD. "
            "The draft also uses EUR."
        )
    if wrong == "USD" and re.search(r"\bUSD\b|\$", text):
        return (
            f"Client country {brief.client_country} requires EUR. "
            "The draft also uses USD."
        )
    return None


def _sla_violation(text: str) -> str | None:
    for line in text.splitlines():
        if _SLA.search(line) is None or _PERCENT.search(line) is None:
            continue
        if re.search(r"not stated|clarification is required|not provided", line, re.IGNORECASE):
            continue
        return None
    return (
        "State the on-time delivery SLA as a percentage on its own line, "
        "for example 'On-time delivery SLA: 97%'. Use a percentage already present in the Part 1 handoff. "
        "Do not invent one."
    )


def _returns_violation(text: str) -> str | None:
    for pattern in (_UNDER_48, _WITHIN_HOURS, _HYPHEN_HOURS, _FAST_RETURNS):
        for match in pattern.finditer(text):
            if not _returns_nearby(text, match.start(), match.end()):
                continue
            window = text[max(0, match.start() - 48) : match.start()]
            if _negated(window):
                continue
            if pattern in {_WITHIN_HOURS, _HYPHEN_HOURS}:
                hours = int(match.group(1))
                if hours >= 48:
                    continue
                return (
                    f"The draft promises returns processing in {hours} hours. "
                    "Remove that promise and state that returns processing will not be promised in under 48 hours."
                )
            phrase = match.group(0)
            return (
                f"The draft promises returns processing '{phrase}'. "
                "Remove that promise and state that returns processing will not be promised in under 48 hours."
            )
    return None


def _discount_violation(text: str) -> str | None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        lowered = line.lower()
        if "volume" not in lowered or "discount" not in lowered or "|" not in line:
            continue
        if index + 1 >= len(lines) or _TABLE_SEPARATOR.search(lines[index + 1]) is None:
            continue
        if index + 2 < len(lines) and "|" in lines[index + 2]:
            return None
    return (
        "Add a Markdown volume-based discount tier table with columns "
        "'Monthly volume tier' and 'Discount', a separator row, and one data row. "
        "Copy tiers from intake. If none were stated, put 'Not stated' in both cells."
    )


def _carrier_violation(text: str) -> str | None:
    chunks = re.split(r"\n+|(?<=[.!?])\s+", text)
    for chunk in chunks:
        if _CARRIER.search(chunk) and _PRICE.search(chunk):
            return (
                "Remove the named carrier rate from this sentence: "
                f"{chunk.strip()} "
                "Only final pricing offered to the client may appear."
            )
    return None


def evaluate(text: str, brief: GenerationInput) -> dict:
    """Check the five TrackFlow rules. Violations carry stable rule ids."""
    checks = (
        (TRACKFLOW_CURRENCY, _currency_violation(text, brief)),
        (TRACKFLOW_DELIVERY_SLA, _sla_violation(text)),
        (TRACKFLOW_RETURNS_MIN_48H, _returns_violation(text)),
        (TRACKFLOW_VOLUME_DISCOUNT_TIERS, _discount_violation(text)),
        (TRACKFLOW_NO_CARRIER_RATE_DISCLOSURE, _carrier_violation(text)),
    )
    violations = [
        {"rule_id": rule_id, "message": message}
        for rule_id, message in checks
        if message is not None
    ]
    return {
        "pass": not violations,
        "rule_ids": [item["rule_id"] for item in violations],
        "violations": violations,
        "rules_checked": list(RULE_IDS),
    }
