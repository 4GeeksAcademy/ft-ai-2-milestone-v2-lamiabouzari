"""Reusable TrackFlow incident validation and analysis logic.

This module contains no CLI or web framework concerns so it can be imported by
both the command-line tool and a future FastAPI endpoint.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
import re
from typing import Iterable, Mapping

REQUIRED_FIELDS = (
    "incident_id",
    "date",
    "country",
    "customer_type",
    "tracking_number",
    "carrier",
    "category",
    "description",
    "status",
    "customer_email",
    "satisfaction_score",
)

VALID_COUNTRIES = frozenset({"US", "ES"})
VALID_CARRIERS_BY_COUNTRY = {
    "US": frozenset({"UPS", "FEDEX", "DHL_US"}),
    "ES": frozenset({"MRW", "SEUR", "DHL_ES", "LOCAL_ES"}),
}
VALID_CATEGORIES = frozenset(
    {"LOST_PARCEL", "DELAYED_DELIVERY", "WRONG_ADDRESS", "RETURN_REQUEST", "DAMAGE"}
)
VALID_STATUSES = frozenset({"OPEN", "CLOSED", "DISCARDED"})
VALID_CUSTOMER_TYPES = frozenset({"B2B", "B2C"})

INCIDENT_ID_PATTERN = re.compile(r"^TRF-\d{6}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

REASON_INCIDENT_ID = "invalid_incident_id"
REASON_DUPLICATE_INCIDENT_ID = "duplicate_incident_id"
REASON_DATE = "invalid_date"
REASON_CUSTOMER_TYPE = "invalid_customer_type"
REASON_COUNTRY = "invalid_country"
REASON_CARRIER = "invalid_carrier"
REASON_TRACKING_NUMBER = "invalid_tracking_number"
REASON_CATEGORY = "invalid_category"
REASON_DESCRIPTION = "invalid_description"
REASON_CUSTOMER_EMAIL = "invalid_customer_email"
REASON_CLOSED_SCORE = "closed_without_satisfaction_score"
REASON_SATISFACTION_SCORE = "invalid_satisfaction_score"
REASON_STATUS = "invalid_status"


@dataclass(frozen=True)
class ValidationResult:
    """Validation outcome without exposing any source row or personal data."""

    valid: bool
    reasons: tuple[str, ...] = ()
    satisfaction_score: int | None = None


@dataclass(frozen=True)
class AnalysisReport:
    """Aggregate-only analysis result suitable for CLI or API serialization."""

    total_records: int
    valid_records: int
    invalid_records: int
    invalid_by_reason: dict[str, int]
    category_breakdown: dict[str, int]
    category_percentages: dict[str, float]
    status_breakdown: dict[str, int]
    status_percentages: dict[str, float]
    country_breakdown: dict[str, int]
    country_percentages: dict[str, float]
    closed_scored_incident_count: int
    average_satisfaction: float | None
    score_distribution: dict[int, int]


def _text(row: Mapping[str, object], field: str) -> str:
    value = row.get(field, "")
    return "" if value is None else str(value).strip()


def validate_incident(row: Mapping[str, object]) -> ValidationResult:
    """Validate one incident and return all applicable, non-sensitive reasons."""

    incident_id = _text(row, "incident_id")
    incident_date = _text(row, "date")
    customer_type = _text(row, "customer_type")
    country = _text(row, "country")
    carrier = _text(row, "carrier")
    tracking_number = _text(row, "tracking_number")
    category = _text(row, "category")
    description = _text(row, "description")
    status = _text(row, "status")
    email = _text(row, "customer_email")
    raw_score = _text(row, "satisfaction_score")
    reasons: list[str] = []

    if not INCIDENT_ID_PATTERN.fullmatch(incident_id):
        reasons.append(REASON_INCIDENT_ID)
    if not DATE_PATTERN.fullmatch(incident_date):
        reasons.append(REASON_DATE)
    else:
        try:
            date.fromisoformat(incident_date)
        except ValueError:
            reasons.append(REASON_DATE)
    if customer_type not in VALID_CUSTOMER_TYPES:
        reasons.append(REASON_CUSTOMER_TYPE)
    if country not in VALID_COUNTRIES:
        reasons.append(REASON_COUNTRY)
    if not carrier or carrier not in VALID_CARRIERS_BY_COUNTRY.get(country, frozenset()):
        reasons.append(REASON_CARRIER)
    if len(tracking_number) < 8:
        reasons.append(REASON_TRACKING_NUMBER)
    if category not in VALID_CATEGORIES:
        reasons.append(REASON_CATEGORY)
    if len(description) < 5:
        reasons.append(REASON_DESCRIPTION)
    if not email or "@" not in email:
        reasons.append(REASON_CUSTOMER_EMAIL)
    if status not in VALID_STATUSES:
        reasons.append(REASON_STATUS)

    score: int | None = None
    if raw_score:
        try:
            score = int(raw_score)
        except ValueError:
            reasons.append(REASON_SATISFACTION_SCORE)
        else:
            if not 1 <= score <= 5:
                reasons.append(REASON_SATISFACTION_SCORE)
    elif status == "CLOSED":
        reasons.append(REASON_CLOSED_SCORE)

    return ValidationResult(not reasons, tuple(reasons), score if not reasons else None)


def _percentages(counts: Mapping[object, int], denominator: int) -> dict[object, float]:
    if not denominator:
        return {key: 0.0 for key in counts}
    return {key: round(value / denominator * 100, 2) for key, value in counts.items()}


def analyze_incidents(rows: Iterable[Mapping[str, object]]) -> AnalysisReport:
    """Validate and aggregate incident rows, excluding every invalid row."""

    total = 0
    valid = 0
    invalid_by_reason: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    countries: Counter[str] = Counter()
    scores: Counter[int] = Counter()
    satisfaction_total = 0
    satisfaction_count = 0
    closed_scored = 0
    seen_incident_ids: set[str] = set()

    for row in rows:
        total += 1
        result = validate_incident(row)
        incident_id = _text(row, "incident_id")
        if incident_id and incident_id in seen_incident_ids:
            result = ValidationResult(
                valid=False,
                reasons=(*result.reasons, REASON_DUPLICATE_INCIDENT_ID),
            )
        if incident_id:
            seen_incident_ids.add(incident_id)
        if not result.valid:
            invalid_by_reason.update(result.reasons)
            continue

        valid += 1
        category = _text(row, "category")
        status = _text(row, "status")
        country = _text(row, "country")
        categories[category] += 1
        statuses[status] += 1
        countries[country] += 1
        if result.satisfaction_score is not None:
            scores[result.satisfaction_score] += 1
            satisfaction_total += result.satisfaction_score
            satisfaction_count += 1
            if status == "CLOSED":
                closed_scored += 1

    category_breakdown = {category: categories[category] for category in sorted(VALID_CATEGORIES)}
    status_breakdown = {status: statuses[status] for status in sorted(VALID_STATUSES)}
    country_breakdown = {country: countries[country] for country in sorted(VALID_COUNTRIES)}
    score_distribution = {score: scores[score] for score in range(1, 6)}

    return AnalysisReport(
        total_records=total,
        valid_records=valid,
        invalid_records=total - valid,
        invalid_by_reason=dict(sorted(invalid_by_reason.items())),
        category_breakdown=category_breakdown,
        category_percentages=_percentages(category_breakdown, valid),
        status_breakdown=status_breakdown,
        status_percentages=_percentages(status_breakdown, valid),
        country_breakdown=country_breakdown,
        country_percentages=_percentages(country_breakdown, valid),
        closed_scored_incident_count=closed_scored,
        average_satisfaction=(round(satisfaction_total / satisfaction_count, 2) if satisfaction_count else None),
        score_distribution=score_distribution,
    )
