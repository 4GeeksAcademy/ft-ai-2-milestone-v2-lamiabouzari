"""Deterministic TrackFlow guardrails for untrusted content and disclosures.

System instructions stay in the agent. User text, retrieved documents, and
MCP/tool payloads are data. This module never sends that data to a model and
never records question text, order identifiers, or document contents.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

FAILURE_TYPES = ("security", "content", "structural")

OUTPUT_BLOCKED_MESSAGE = (
    "I can't share that information. I can help with your shipment tracking, "
    "returns, SLA policies, and delivery incidents."
)

COUNTRY_POLICIES = {
    "United States": (
        "United States return and SLA policy: shipments in the United States, including Los Angeles, "
        "follow only United States return and SLA rules. A different country's return window, refund practice, "
        "or delivery commitment is not applied to these shipments."
    ),
    "Spain": (
        "Spain return and SLA policy: shipments in Spain, including Zaragoza, "
        "follow only Spain return and SLA rules. A different country's return window, refund practice, "
        "or delivery commitment is not applied to these shipments."
    ),
}

_EVENTS: list[dict[str, str]] = []

_BRACKET_ROLE = re.compile(
    r"\[\s*(system|developer|assistant|instruction|policy)\s*\]\s*:?",
    re.IGNORECASE,
)
_BARE_ROLE = re.compile(
    r"(?:^|\n)\s*(system|developer|instruction)\s*:\s*",
    re.IGNORECASE,
)
_OVERRIDE = re.compile(
    r"\b(ignore|disregard|forget|override|bypass)\b.{0,80}\b"
    r"(previous|prior|above|earlier|system|rules?|instructions?|policy|policies)\b",
    re.IGNORECASE,
)
_ORDER_ID = re.compile(
    r"\border\s*(?:number|id|no\.?)?\s*#\s*(\d{4,})\b"
    r"|\border\s*(?:number|id|no\.?)\s*#?\s*(\d{4,})\b"
    r"|\border\s+#?(\d{4,})\b",
    re.IGNORECASE,
)
_ORDER_MENTION = re.compile(r"\border\s*#\s*(\d{4,})\b", re.IGNORECASE)
_REQUESTED_POLICY = re.compile(
    r"\b(?:apply|use|switch to|follow)\s+(?:the\s+)?"
    r"(?P<country>spain|spanish|united states|u\.s\.a\.|u\.s\.|usa|american)\b"
    r"|\b(?P<country2>spain|spanish|united states|american)(?:'s|’s)\s+"
    r"(?:return|sla|delivery)\b",
    re.IGNORECASE,
)
_ORDER_PLACE = re.compile(
    r"\b(?:in|from|at)\s+"
    r"(?P<place>los angeles|zaragoza|the united states|united states|spain|u\.s\.a\.|usa)\b",
    re.IGNORECASE,
)
_COUNTRY_WORDS = {
    "spain": "Spain",
    "spanish": "Spain",
    "zaragoza": "Spain",
    "united states": "United States",
    "usa": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "american": "United States",
    "los angeles": "United States",
}
_PRETTY_PLACE = {
    "los angeles": "Los Angeles",
    "zaragoza": "Zaragoza",
    "spain": "Spain",
    "united states": "United States",
    "usa": "USA",
    "u.s.": "U.S.",
    "u.s.a.": "USA",
}
_CONTROL_KEYS = {
    "system",
    "instruction",
    "instructions",
    "prompt",
    "developer",
    "policy",
    "role",
}
_DOC_FIELDS = ("source_document", "section", "text", "score", "company")
_TOOL_FIELDS = (
    "found",
    "incident_id",
    "status",
    "category",
    "origin",
    "created_at",
    "updated_at",
    "error",
)
_SENSITIVE_OUTPUT = (
    re.compile(r"\bnegotiated\b.{0,48}\b(?:carrier\s+)?rates?\b", re.IGNORECASE),
    re.compile(
        r"\b(?:carrier|contract(?:ed)?)\s+rates?\b.{0,48}\b(?:negotiated|confidential|unpublished)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bcommercial terms\b", re.IGNORECASE),
    re.compile(
        r"\b(?:b2b|business[- ]to[- ]business)\b.{0,40}\b(?:terms|pricing|contract)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bexact warehouse\b|\bwarehouse (?:is )?located at\b|\bwarehouse address\b", re.IGNORECASE),
    re.compile(
        r"\b\d{1,6}\s+[A-Za-z0-9][A-Za-z0-9.'-]*(?:\s+[A-Za-z0-9][A-Za-z0-9.'-]*){0,4}\s+"
        r"(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|way)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\binternal (?:warehouse )?routes?\b|\bwarehouse routes?\b", re.IGNORECASE),
    re.compile(r"\b(?:aisle|dock(?:\s+door)?|bin)\s+[A-Z0-9]+(?:-[A-Z0-9]+)?\b", re.IGNORECASE),
    re.compile(r"\b(?:system prompt|developer prompt|internal instructions)\b", re.IGNORECASE),
    re.compile(r"you are a trackflow salesperson", re.IGNORECASE),
    re.compile(r"mandatory trackflow safeguards", re.IGNORECASE),
    re.compile(r"\[\s*system\s*\]", re.IGNORECASE),
    re.compile(
        r"\b(?:another|other|different)\s+customer(?:'s|’s)?\b.{0,60}\b(?:order|tracking|shipment)\b",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class SupportSession:
    """Authenticated caller for order checks.

    ``subject`` is the same kind of identity MCP auth stores on a verified
    token. ``owned_order_ids`` lists the orders that identity may read.
    """

    subject: str
    scopes: frozenset[str] = frozenset()
    owned_order_ids: frozenset[str] = frozenset()


def record_guardrail(guardrail: str, action: str, failure_type: str) -> dict[str, str]:
    """Count one block, redirect, or quarantine without storing customer data."""
    if failure_type not in FAILURE_TYPES:
        raise ValueError(f"Unknown guardrail failure type: {failure_type}")
    event = {"guardrail": guardrail, "action": action, "failure_type": failure_type}
    _EVENTS.append(event)
    logger.info(
        "guardrail_trigger guardrail=%s action=%s failure_type=%s",
        guardrail,
        action,
        failure_type,
    )
    return dict(event)


def reset_guardrail_metrics() -> None:
    """Clear in-process counters. Tests call this between cases."""
    _EVENTS.clear()


def guardrail_events() -> list[dict[str, str]]:
    """Return copies of recorded triggers for the current process."""
    return [dict(event) for event in _EVENTS]


def guardrail_summary() -> dict[str, Any]:
    """Return totals grouped by guardrail, action, and failure type."""
    by_guardrail: dict[str, int] = {}
    by_action: dict[str, int] = {}
    by_failure_type = {name: 0 for name in FAILURE_TYPES}
    for event in _EVENTS:
        by_guardrail[event["guardrail"]] = by_guardrail.get(event["guardrail"], 0) + 1
        by_action[event["action"]] = by_action.get(event["action"], 0) + 1
        failure_type = event["failure_type"]
        by_failure_type[failure_type] = by_failure_type.get(failure_type, 0) + 1
    return {
        "total": len(_EVENTS),
        "by_guardrail": by_guardrail,
        "by_action": by_action,
        "by_failure_type": by_failure_type,
    }


def _contains_external_instruction(text: str) -> bool:
    return bool(_BRACKET_ROLE.search(text) or _BARE_ROLE.search(text) or _OVERRIDE.search(text))


def isolate_untrusted_text(text: str) -> tuple[str, bool]:
    """Keep instruction-shaped text as ordinary data.

    Role markers such as ``[SYSTEM]`` are rewritten so they cannot be read as
    a system message. The surrounding words stay intact.
    """
    if not text or not _contains_external_instruction(text):
        return text, False
    neutralized = _BRACKET_ROLE.sub(lambda match: f"[untrusted-data:{match.group(1).lower()}]", text)
    neutralized = _BARE_ROLE.sub(lambda match: f"[untrusted-data:{match.group(1).lower()}] ", neutralized)
    return f"[untrusted external data] {neutralized}", True


def _record_has_instruction(record: dict[str, Any]) -> bool:
    for key, value in record.items():
        if str(key).lower() in _CONTROL_KEYS:
            return True
        if isinstance(value, str) and _contains_external_instruction(value):
            return True
    return False


def isolate_documents(documents: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    """Project retrieved documents onto data fields and neutralize role markers.

    Clean documents are returned unchanged. Instruction channels (``system``,
    ``instructions``, and similar keys) are dropped instead of forwarded.
    """
    if not documents or not any(_record_has_instruction(document) for document in documents):
        return documents, False

    isolated: list[dict[str, Any]] = []
    for document in documents:
        if not _record_has_instruction(document):
            isolated.append(document)
            continue
        cleaned: dict[str, Any] = {}
        for key in _DOC_FIELDS:
            if key not in document:
                continue
            value = document[key]
            if isinstance(value, str):
                value, _was_injected = isolate_untrusted_text(value)
            cleaned[key] = value
        isolated.append(cleaned)
    return isolated, True


def isolate_tool_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Project one MCP/tool payload onto its known fields.

    Extra instruction keys are discarded. String fields that contain role
    markers stay in the payload as neutralized data.
    """
    if not isinstance(payload, dict) or not _record_has_instruction(payload):
        return payload, False

    isolated: dict[str, Any] = {}
    for key in _TOOL_FIELDS:
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, str):
            value, _was_injected = isolate_untrusted_text(value)
        isolated[key] = value
    return isolated, True


def extract_order_id(question: str) -> str | None:
    """Return the first order number in a support question, if one is present."""
    match = _ORDER_ID.search(question)
    if match is None:
        return None
    return next(group for group in match.groups() if group)


def output_is_sensitive(answer: str, *, owned_order_ids: frozenset[str] | set[str] = frozenset()) -> bool:
    """True when an answer discloses restricted TrackFlow or customer data."""
    if any(pattern.search(answer) for pattern in _SENSITIVE_OUTPUT):
        return True
    owned = {str(order_id) for order_id in owned_order_ids}
    return any(order_id not in owned for order_id in _ORDER_MENTION.findall(answer))


def apply_output_guardrail(
    answer: str,
    *,
    owned_order_ids: frozenset[str] | set[str] = frozenset(),
) -> tuple[str, dict[str, str] | None]:
    """Replace a sensitive answer with a fixed refusal. Clean answers pass through."""
    if not output_is_sensitive(answer, owned_order_ids=owned_order_ids):
        return answer, None
    event = record_guardrail("output_sensitive", "block", "security")
    return OUTPUT_BLOCKED_MESSAGE, event


def _canonical_country(label: str) -> str | None:
    key = re.sub(r"\s+", " ", label.lower()).strip()
    if key.startswith("the "):
        key = key[4:]
    return _COUNTRY_WORDS.get(key)


def _pretty_place(label: str) -> str:
    key = re.sub(r"\s+", " ", label.lower()).strip()
    if key.startswith("the "):
        key = key[4:]
    return _PRETTY_PLACE.get(key, label.strip())


def detect_country_policy_conflict(question: str) -> dict[str, str] | None:
    """Detect a request to apply one country's policy to another country's order.

    A shipment location decides the country. Los Angeles is the United States.
    Zaragoza is Spain. Matching country requests are left to the normal flow.
    """
    requested_match = _REQUESTED_POLICY.search(question)
    if requested_match is None:
        return None
    requested_token = requested_match.group("country") or requested_match.group("country2") or ""
    requested = _canonical_country(requested_token)
    if requested is None:
        return None

    places: list[tuple[str, str]] = []
    for match in _ORDER_PLACE.finditer(question):
        country = _canonical_country(match.group("place"))
        if country is None:
            continue
        places.append((match.group("place"), country))
    actual_countries = {country for _place, country in places}
    if len(actual_countries) != 1:
        return None
    actual = next(iter(actual_countries))
    if actual == requested:
        return None

    place_label = places[0][0]
    for place, _country in places:
        if place.lower() in {"los angeles", "zaragoza"}:
            place_label = place
            break
    return {
        "actual_country": actual,
        "requested_country": requested,
        "place": _pretty_place(place_label),
    }


def country_policy_answer(*, actual_country: str, requested_country: str, place: str) -> str:
    """Reject a cross-country policy switch and state only the order's policy."""
    policy = COUNTRY_POLICIES[actual_country]
    return (
        f"I can't apply {requested_country}'s return or SLA policy to this order. "
        f"{place} is in the {actual_country}, so only the {actual_country} policy is enforced. "
        f"{policy}"
    )
