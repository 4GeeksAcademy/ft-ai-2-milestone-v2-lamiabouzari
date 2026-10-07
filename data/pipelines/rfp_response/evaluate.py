"""Run readability, relevance, and compliance concurrently, then merge."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from data.pipelines.rfp_response.evaluators import compliance, readability, relevance
from data.pipelines.rfp_response.schemas import GenerationInput


def _feedback(readability_result: dict, relevance_result: dict, compliance_result: dict) -> str:
    lines: list[str] = []
    for problem in readability_result.get("details", {}).get("problems") or []:
        lines.append(f"Readability: {problem}")
    for aspect in relevance_result.get("missing_aspects") or []:
        lines.append(f"Missing key aspect: {aspect}")
    for violation in compliance_result.get("violations") or []:
        lines.append(f"Compliance {violation['rule_id']}: {violation['message']}")
    if not lines:
        return "All readability, relevance, and compliance checks passed."
    return "\n".join(lines)


def merge_evaluation(
    department_id: str,
    readability_result: dict,
    relevance_result: dict,
    compliance_result: dict,
    iteration: int,
) -> dict:
    """overall_pass is true only when every evaluator passed."""
    overall = bool(
        readability_result.get("pass")
        and relevance_result.get("pass")
        and compliance_result.get("pass")
    )
    return {
        "department_id": department_id,
        "readability": readability_result,
        "relevance": relevance_result,
        "compliance": compliance_result,
        "overall_pass": overall,
        "feedback_for_generator": _feedback(readability_result, relevance_result, compliance_result),
        "iterations": iteration,
    }


def evaluate_section(draft: str, brief: GenerationInput, iteration: int) -> dict:
    """Evaluate one draft. Evaluators return new dicts and do not share a result object."""
    aspects = list(brief.key_aspects)
    with ThreadPoolExecutor(max_workers=3) as pool:
        readability_future = pool.submit(readability.evaluate, draft)
        relevance_future = pool.submit(relevance.evaluate, draft, aspects)
        compliance_future = pool.submit(compliance.evaluate, draft, brief)
        readability_result = readability_future.result()
        relevance_result = relevance_future.result()
        compliance_result = compliance_future.result()
    return merge_evaluation(
        brief.department_id,
        readability_result,
        relevance_result,
        compliance_result,
        iteration,
    )
