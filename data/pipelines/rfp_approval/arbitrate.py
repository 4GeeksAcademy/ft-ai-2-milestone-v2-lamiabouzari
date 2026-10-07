"""Deterministic TrackFlow arbitration. No model votes on a conflict."""

from __future__ import annotations

import re
from typing import Any

from data.pipelines.rfp_approval.config import COMMERCIAL_DIRECTOR
from data.pipelines.rfp_intake.departments import DEPARTMENTS, currency_for_country
from data.pipelines.rfp_response.evaluators.compliance import (
    TRACKFLOW_RETURNS_MIN_48H,
    _returns_violation,
)

_CAPACITY = re.compile(
    r"(?:committed capacity|onboarding throughput)\D{0,40}?(\d[\d,]*)",
    re.IGNORECASE,
)
_VOLUME = re.compile(
    r"(?:assumed monthly volume|monthly volume)\D{0,40}?(\d[\d,]*)",
    re.IGNORECASE,
)
_OFFER = re.compile(r"Offer currency:\s*(USD|EUR)\b", re.IGNORECASE)


def _number(raw: str) -> int:
    return int(raw.replace(",", ""))


def committed_capacity(draft: str) -> int | None:
    match = _CAPACITY.search(draft or "")
    if match is None:
        return None
    return _number(match.group(1))


def assumed_volume(draft: str) -> int | None:
    match = _VOLUME.search(draft or "")
    if match is None:
        return None
    return _number(match.group(1))


def offer_currency(draft: str) -> str | None:
    match = _OFFER.search(draft or "")
    if match is None:
        return None
    return match.group(1).upper()


def cap_volume_text(text: str, capacity: int) -> str:
    """Apply the fixed volume cap to one intake line. Other numbers stay put."""

    def replace(match: re.Match[str]) -> str:
        return match.group(0).replace(match.group(1), str(capacity), 1)

    return _VOLUME.sub(replace, text, count=1)


def promises_returns_under_48h(draft: str) -> bool:
    return _returns_violation(draft or "") is not None


def detect_conflicts(sections: list[dict[str, Any]], client_country: str | None) -> list[dict[str, Any]]:
    """Read structured figures and currency lines. Return fixed resolutions."""
    by_id = {str(item["department_id"]): item for item in sections}
    found: list[dict[str, Any]] = []
    warehouse = by_id.get("warehouse")
    lastmile = by_id.get("lastmile")
    if warehouse and lastmile:
        capacity = committed_capacity(str(warehouse.get("draft_content") or ""))
        volume = assumed_volume(str(lastmile.get("draft_content") or ""))
        if capacity is not None and volume is not None and volume > capacity:
            found.append(
                {
                    "conflict_id": "volume-vs-capacity",
                    "departments": ["warehouse", "lastmile"],
                    "arbiter": COMMERCIAL_DIRECTOR,
                    "resolution_rule": (
                        f"Cap proposal volume to warehouse capacity of {capacity}. "
                        "Last mile must revise quoted volume and cost downward."
                    ),
                    "next": "request_changes:lastmile",
                    "capacity": capacity,
                }
            )
    for department_id, section in by_id.items():
        draft = str(section.get("draft_content") or "")
        if not promises_returns_under_48h(draft):
            continue
        arbiter = DEPARTMENTS["reverse"]["contact"] if department_id == "reverse" else COMMERCIAL_DIRECTOR
        found.append(
            {
                "conflict_id": "returns-sla-breach",
                "departments": [department_id],
                "arbiter": arbiter,
                "rule_id": TRACKFLOW_RETURNS_MIN_48H,
                "resolution_rule": (
                    "Remove the returns promise under 48 hours. "
                    "State that returns processing will not be promised in under 48 hours."
                ),
                "next": f"request_changes:{department_id}",
            }
        )
    required = currency_for_country(client_country)
    offers = {
        department_id: offer_currency(str(section.get("draft_content") or ""))
        for department_id, section in by_id.items()
    }
    quoted = {code for code in offers.values() if code}
    offending: list[str] = []
    if required in {"USD", "EUR"}:
        offending = [department_id for department_id, code in offers.items() if code != required]
    elif len(quoted) > 1:
        offending = [department_id for department_id, code in offers.items() if code]
    if offending:
        found.append(
            {
                "conflict_id": "currency-mismatch",
                "departments": offending,
                "arbiter": COMMERCIAL_DIRECTOR,
                "resolution_rule": (
                    f"Rewrite offending sections to {required if required in {'USD', 'EUR'} else 'one offer currency'}."
                ),
                "next": "request_changes:" + ",".join(offending),
                "required_currency": required if required in {"USD", "EUR"} else None,
            }
        )
    return found
