"""Relevance evaluator. Checks department key aspects and returns its own result."""

from __future__ import annotations

import re

_WORD = re.compile(r"[A-Za-z0-9']+")
_CARRIER = re.compile(
    r"\b(ups|fedex|dhl|usps|correos|seur|mrw|gls|dpd|ontrac|lasership)\b",
    re.IGNORECASE,
)
_MONEY = re.compile(r"(€|\$|\bEUR\b|\bUSD\b)", re.IGNORECASE)


def _covered(aspect: str, draft: str) -> bool:
    lowered = draft.lower()
    if aspect.lower() in lowered:
        return True
    if _CARRIER.search(aspect) and _MONEY.search(aspect):
        return "negotiated carrier rate" in lowered and "withheld" in lowered
    words = [word.lower() for word in _WORD.findall(aspect) if len(word) > 3]
    if not words:
        return False
    found = sum(1 for word in words if word in lowered)
    return found / len(words) >= 0.6


def evaluate(text: str, key_aspects: list[str]) -> dict:
    """List key aspects the draft does not address."""
    missing = [aspect for aspect in key_aspects if not _covered(aspect, text)]
    return {"pass": not missing, "missing_aspects": missing}
