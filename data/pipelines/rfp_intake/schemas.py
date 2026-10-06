"""Structured outputs shared by the intake agents."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DepartmentKey = Literal["warehouse", "lastmile", "reverse"]
CurrencyContext = Literal["EUR", "USD", "UNKNOWN"]


class Classification(BaseModel):
    is_rfp: bool
    document_style: Literal["formal", "informal", "not_applicable"]
    reason: str


class RfpMetadataDraft(BaseModel):
    client_name: str | None = None
    client_country: str | None = None
    services_requested: list[str] = Field(default_factory=list)
    monthly_volume: str | None = None
    deadline: str | None = None
    budget_range: str | None = None
    departments_needed: list[DepartmentKey] = Field(default_factory=list)
    currency_context: CurrencyContext = "UNKNOWN"
    readability: dict[str, float | int] = Field(default_factory=dict)


class Workstream(BaseModel):
    department_key: DepartmentKey
    department_name: str
    contact: str
    objective: str


class OrchestratorPlan(BaseModel):
    departments: list[Workstream]
    currency_context: CurrencyContext


class WorkerResult(BaseModel):
    department_key: DepartmentKey
    department_name: str
    contact: str
    key_aspects: list[str]
    open_questions: list[str]


class DepartmentAsk(BaseModel):
    department_key: DepartmentKey
    department_name: str
    contact: str
    needs: str
    questions: list[str]


class SynthesizerResult(BaseModel):
    sales_summary: str
    department_asks: list[DepartmentAsk]
