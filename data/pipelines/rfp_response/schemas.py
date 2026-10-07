"""Inputs and outcomes for department response generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GenerationInput:
    """Facts a single department generator is allowed to use."""

    department_id: str
    department_name: str
    contact: str
    client_name: str | None
    client_country: str | None
    currency_context: str
    key_aspects: list[str]
    open_questions: list[str]
    workstream: dict[str, Any]
    services_requested: list[str] = field(default_factory=list)
    monthly_volume: str | None = None
    deadline: str | None = None
    budget_range: str | None = None
    feedback: str | None = None
    iteration: int = 1


@dataclass
class DepartmentOutcome:
    """Final draft and evaluation for one active department."""

    department_id: str
    draft_content: str
    evaluation: dict[str, Any]
    needs_human_review: bool
