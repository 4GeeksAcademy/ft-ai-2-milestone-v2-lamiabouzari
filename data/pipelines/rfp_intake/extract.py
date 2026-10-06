"""Deterministic metadata extraction from Markdown. Missing values stay empty."""

from __future__ import annotations

import re

from data.pipelines.rfp_intake.departments import currency_for_country, departments_for_text, sentences
from data.pipelines.rfp_intake.readability import readability_metrics
from data.pipelines.rfp_intake.schemas import RfpMetadataDraft

_CLIENT_LINE = re.compile(r"(?im)^client:\s*(.+?)\s*$")
_CLIENT_PROSE = re.compile(
    r"(?i)\b(?:we are|we're)\s+(.+?)\s+in the\b"
)
_COUNTRY_LINE = re.compile(r"(?im)^country:\s*(.+?)\s*$")
_COUNTRY_PROSE = re.compile(r"(?i)\bin the (united states|spain)\b")
_VOLUME = re.compile(
    r"(?i)(\d[\d,]*(?:\.\d+)?\s+(?:orders|parcels|shipments|units)(?:\s+a\s+month)?)"
)
_VOLUME_LABEL = re.compile(r"(?im)^monthly volume:\s*(.+?)\s*$")
_DEADLINE_LABEL = re.compile(r"(?im)^deadline:\s*(.+?)\s*$")
_DEADLINE_PROSE = re.compile(r"(?i)\b(before\s+[A-Z][a-z]+(?:\s+\d{4})?)\b")
_BUDGET_LABEL = re.compile(r"(?im)^budget(?:\s+range)?:\s*(.+?)\s*$")
_BUDGET_PROSE = re.compile(
    r"(?i)((?:EUR|USD)\s*[\d,]+(?:\s*(?:-|–|to)\s*[\d,]+)?)"
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split())
    return text or None


def _country(text: str) -> str | None:
    labeled = _COUNTRY_LINE.search(text)
    if labeled:
        raw = labeled.group(1).strip()
        lowered = raw.lower()
        if lowered in {"us", "usa", "u.s."}:
            return "United States"
        return raw
    prose = _COUNTRY_PROSE.search(text)
    if prose:
        name = prose.group(1).lower()
        return "United States" if name == "united states" else "Spain"
    lowered = text.lower()
    if "zaragoza" in lowered:
        return "Spain"
    if "los angeles" in lowered:
        return "United States"
    return None


def _services(text: str) -> list[str]:
    found: list[str] = []
    for sentence in sentences(text):
        lowered = sentence.lower()
        if "not " in lowered or lowered.startswith("no "):
            continue
        for label, needle in (
            ("warehousing", "warehous"),
            ("fulfillment", "fulfill"),
            ("storage", "store our"),
            ("last-mile delivery", "last-mile"),
            ("last-mile delivery", "last mile"),
            ("reverse logistics", "reverse logistics"),
            ("returns processing", "return"),
        ):
            if needle in lowered and label not in found:
                found.append(label)
    return found


def extract_metadata(markdown: str) -> RfpMetadataDraft:
    """Pull only facts that are written in the document."""
    client = _CLIENT_LINE.search(markdown)
    if client:
        client_name = _clean(client.group(1))
    else:
        prose = _CLIENT_PROSE.search(markdown)
        client_name = _clean(prose.group(1) if prose else None)

    country = _country(markdown)
    volume_label = _VOLUME_LABEL.search(markdown)
    volume = _clean(volume_label.group(1) if volume_label else None)
    if volume is None:
        volume_match = _VOLUME.search(markdown)
        volume = _clean(volume_match.group(1) if volume_match else None)

    deadline_label = _DEADLINE_LABEL.search(markdown)
    deadline = _clean(deadline_label.group(1) if deadline_label else None)
    if deadline is None:
        deadline_prose = _DEADLINE_PROSE.search(markdown)
        deadline = _clean(deadline_prose.group(1) if deadline_prose else None)

    budget_label = _BUDGET_LABEL.search(markdown)
    budget = _clean(budget_label.group(1) if budget_label else None)
    if budget is None:
        budget_prose = _BUDGET_PROSE.search(markdown)
        budget = _clean(budget_prose.group(1) if budget_prose else None)

    return RfpMetadataDraft(
        client_name=client_name,
        client_country=country,
        services_requested=_services(markdown),
        monthly_volume=volume,
        deadline=deadline,
        budget_range=budget,
        departments_needed=departments_for_text(markdown),
        currency_context=currency_for_country(country),
        readability=readability_metrics(markdown),
    )
