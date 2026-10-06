"""Department worker agents. One worker sees one department extract."""

from __future__ import annotations

import re

from data.pipelines.rfp_intake.departments import DEPARTMENTS, sentence_requests, sentences
from data.pipelines.rfp_intake.schemas import RfpMetadataDraft, WorkerResult

SYSTEM_PROMPT = """You are one TrackFlow department worker.
Use only the shared metadata and the department extract you were given.
Return key_aspects that restate stated facts, and open_questions for anything missing.
Never invent volumes, prices, capacity, deadlines, or budget figures.
Name the TrackFlow department and its contact. Return JSON for a WorkerResult."""

_NUMBER = re.compile(r"\d[\d,]*")


def relevant_extract(markdown: str, department_key: str) -> str:
    """Sentences that request this department, excluding negated scope."""
    kept = [
        sentence
        for sentence in sentences(markdown)
        if sentence_requests(department_key, sentence)
    ]
    return "\n".join(kept)


def _numbers(text: str) -> set[str]:
    return set(_NUMBER.findall(text))


def decide(department_key: str, metadata: RfpMetadataDraft, extract: str) -> WorkerResult:
    """Produce key aspects and questions without filling missing figures."""
    department = DEPARTMENTS[department_key]
    source = "\n".join(
        part
        for part in (
            extract,
            metadata.client_name or "",
            metadata.client_country or "",
            metadata.monthly_volume or "",
            metadata.deadline or "",
            metadata.budget_range or "",
        )
        if part
    )
    allowed_numbers = _numbers(source)
    aspects: list[str] = []
    for sentence in sentences(extract):
        if _numbers(sentence) - allowed_numbers:
            continue
        aspects.append(sentence)
    if metadata.monthly_volume and _numbers(metadata.monthly_volume) <= allowed_numbers:
        aspects.append(f"Stated monthly volume: {metadata.monthly_volume}")
    if metadata.deadline:
        aspects.append(f"Stated deadline: {metadata.deadline}")
    if metadata.budget_range and _numbers(metadata.budget_range) <= allowed_numbers:
        aspects.append(f"Stated budget range: {metadata.budget_range}")

    questions: list[str] = []
    if not metadata.monthly_volume:
        questions.append("What monthly volume should this department plan for?")
    if not metadata.deadline:
        questions.append("What deadline should this department use?")
    if not metadata.budget_range:
        questions.append("What budget range should Sales confirm for this scope?")
    if not aspects:
        questions.append(
            f"Which stated activities belong to {department['name']}?"
        )

    return WorkerResult(
        department_key=department_key,  # type: ignore[arg-type]
        department_name=department["name"],
        contact=department["contact"],
        key_aspects=aspects,
        open_questions=questions,
    )


def analyze(department_key: str, metadata: RfpMetadataDraft, extract: str) -> WorkerResult:
    """Run one department worker and validate its structured output."""
    from data.pipelines.rfp_intake.llm import complete

    return complete(
        "work",
        {
            "department_key": department_key,
            "metadata": metadata.model_dump(),
            "extract": extract,
        },
        WorkerResult,
    )
