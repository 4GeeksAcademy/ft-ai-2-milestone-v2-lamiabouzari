"""Build generator inputs from a Part 1 routing handoff."""

from __future__ import annotations

import re
from typing import Any

from data.pipelines.rfp_intake.departments import DEPARTMENTS
from data.pipelines.rfp_response.schemas import GenerationInput

_SUMMARY_COUNTRY = re.compile(r"\(([^(),]+),\s*currency\s+[A-Z]+\)")


def _country_from_summary(sales_summary: str) -> str | None:
    match = _SUMMARY_COUNTRY.search(sales_summary or "")
    if match is None:
        return None
    country = match.group(1).strip()
    return country or None


def _asks_by_department(synthesizer: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for ask in synthesizer.get("department_asks") or []:
        if not isinstance(ask, dict):
            continue
        key = ask.get("department_key") or ask.get("department_id")
        if isinstance(key, str):
            indexed[key] = ask
    return indexed


def build_briefs(handoff: dict[str, Any], metadata: dict[str, Any] | None) -> list[GenerationInput]:
    """Active departments are the sections listed on the Part 1 handoff.

    Client country and commercial facts come from the Part 1 metadata row when
    present. The synthesizer summary is only a fallback for the country. The
    PDF is not read.
    """
    meta = metadata or {}
    synthesizer = handoff.get("synthesizer") or {}
    if not isinstance(synthesizer, dict):
        synthesizer = {}
    sales_summary = str(synthesizer.get("sales_summary") or "")
    asks = _asks_by_department(synthesizer)
    country = meta.get("client_country") or _country_from_summary(sales_summary)
    currency = str(handoff.get("currency_context") or meta.get("currency_context") or "UNKNOWN")
    services = list(meta.get("services_requested") or [])
    briefs: list[GenerationInput] = []
    seen: set[str] = set()
    for section in handoff.get("sections") or []:
        if not isinstance(section, dict):
            continue
        key = section.get("department_key") or section.get("department_id")
        if not isinstance(key, str) or key not in DEPARTMENTS or key in seen:
            continue
        seen.add(key)
        department = DEPARTMENTS[key]
        ask = asks.get(key) or {}
        questions = [str(item) for item in section.get("open_questions") or []]
        for question in ask.get("questions") or []:
            text = str(question)
            if text not in questions:
                questions.append(text)
        aspects = [str(item) for item in section.get("key_aspects") or []]
        briefs.append(
            GenerationInput(
                department_id=key,
                department_name=str(section.get("department_name") or department["name"]),
                contact=str(section.get("contact") or department["contact"]),
                client_name=meta.get("client_name"),
                client_country=country,
                currency_context=currency,
                key_aspects=aspects,
                open_questions=questions,
                workstream={
                    "needs": ask.get("needs") or "",
                    "questions": list(ask.get("questions") or []),
                    "sales_summary": sales_summary,
                },
                services_requested=services,
                monthly_volume=meta.get("monthly_volume"),
                deadline=meta.get("deadline"),
                budget_range=meta.get("budget_range"),
            )
        )
    return briefs
