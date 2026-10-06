"""TrackFlow departments that can receive an RFP workstream."""

from __future__ import annotations

import re

DEPARTMENTS: dict[str, dict[str, str]] = {
    "warehouse": {
        "key": "warehouse",
        "name": "Warehouse Operations",
        "contact": "Ana Whitfield",
    },
    "lastmile": {
        "key": "lastmile",
        "name": "Last Mile and Carrier Management",
        "contact": "Carlos Vega",
    },
    "reverse": {
        "key": "reverse",
        "name": "Reverse Logistics",
        "contact": "Sofía Ramos",
    },
}

DEPARTMENT_ORDER = ("warehouse", "lastmile", "reverse")

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "warehouse": (
        "warehouse",
        "warehousing",
        "fulfillment",
        "fulfilment",
        "storage",
        "store our",
        "pick and pack",
        "pick-and-pack",
    ),
    "lastmile": (
        "last-mile",
        "last mile",
        "parcel delivery",
        "deliver to customers",
        "outbound delivery",
        "carrier management",
    ),
    "reverse": (
        "reverse logistics",
        "returns",
        "return processing",
    ),
}

_NEGATION = re.compile(r"\b(not|no|without|never|don't|do not)\b", re.IGNORECASE)


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def sentence_requests(department: str, sentence: str) -> bool:
    """True when a sentence asks for a department and does not negate it."""
    lowered = sentence.lower()
    if not any(keyword in lowered for keyword in _KEYWORDS[department]):
        return False
    return _NEGATION.search(lowered) is None


def departments_for_text(text: str) -> list[str]:
    """Return department keys requested by the text, in stable order."""
    selected: list[str] = []
    chunks = sentences(text)
    for key in DEPARTMENT_ORDER:
        if any(sentence_requests(key, chunk) for chunk in chunks):
            selected.append(key)
    return selected


def currency_for_country(country: str | None) -> str:
    """Map a client country to the currency Sales should use."""
    lowered = (country or "").strip().lower()
    if lowered in {"spain", "españa", "es"}:
        return "EUR"
    if lowered in {"united states", "united states of america", "usa", "us", "u.s."}:
        return "USD"
    return "UNKNOWN"
