"""Bounded generate-and-evaluate loop for one department."""

from __future__ import annotations

from data.pipelines.rfp_response import generators as generator_registry
from data.pipelines.rfp_response.config import MAX_ITERATIONS
from data.pipelines.rfp_response.evaluate import evaluate_section
from data.pipelines.rfp_response.persist import advance_status, save_department_response
from data.pipelines.rfp_response.schemas import DepartmentOutcome, GenerationInput


def _save(
    ticket_id: str,
    brief: GenerationInput,
    *,
    draft_content: str | None,
    evaluation: dict | None,
    iteration: int,
    section_status: str,
    approval_status: str | None,
    needs_human_review: bool,
) -> None:
    save_department_response(
        ticket_id,
        department_id=brief.department_id,
        department_name=brief.department_name,
        contact=brief.contact,
        key_aspects=brief.key_aspects,
        open_questions=brief.open_questions,
        draft_content=draft_content,
        evaluation_results=evaluation,
        iteration_count=iteration,
        section_status=section_status,
        approval_status=approval_status,
        needs_human_review=needs_human_review,
    )


def _error_evaluation(brief: GenerationInput, iteration: int, message: str) -> dict:
    return {
        "department_id": brief.department_id,
        "readability": {"pass": False, "score": 0, "details": {"problems": [message]}},
        "relevance": {"pass": False, "missing_aspects": []},
        "compliance": {"pass": False, "rule_ids": [], "violations": [], "rules_checked": []},
        "overall_pass": False,
        "feedback_for_generator": message,
        "iterations": iteration,
    }


def run_department_loop(ticket_id: str, brief: GenerationInput) -> DepartmentOutcome:
    """Generate, evaluate, and regenerate until the section passes or iterations run out.

    The same department generator receives ``feedback_for_generator`` on the next pass.
    The last draft is kept when the limit is reached.
    """
    feedback: str | None = brief.feedback
    last_draft = ""
    last_evaluation: dict | None = None
    try:
        for iteration in range(1, MAX_ITERATIONS + 1):
            brief.iteration = iteration
            brief.feedback = feedback
            advance_status(ticket_id, "drafting")
            _save(
                ticket_id,
                brief,
                draft_content=last_draft or None,
                evaluation=last_evaluation,
                iteration=iteration,
                section_status="drafting",
                approval_status=None,
                needs_human_review=False,
            )
            last_draft = generator_registry.generate(brief)
            advance_status(ticket_id, "under_evaluation")
            _save(
                ticket_id,
                brief,
                draft_content=last_draft,
                evaluation=last_evaluation,
                iteration=iteration,
                section_status="under_evaluation",
                approval_status=None,
                needs_human_review=False,
            )
            last_evaluation = evaluate_section(last_draft, brief, iteration)
            passed = bool(last_evaluation["overall_pass"])
            _save(
                ticket_id,
                brief,
                draft_content=last_draft,
                evaluation=last_evaluation,
                iteration=iteration,
                section_status="passed" if passed else "under_evaluation",
                approval_status="pending" if passed else None,
                needs_human_review=False,
            )
            if passed:
                return DepartmentOutcome(
                    department_id=brief.department_id,
                    draft_content=last_draft,
                    evaluation=last_evaluation,
                    needs_human_review=False,
                )
            feedback = str(last_evaluation["feedback_for_generator"])
    except Exception as exc:
        iteration = brief.iteration or 1
        message = (
            f"Department {brief.department_id} stopped on iteration {iteration} "
            f"with error: {exc}"
        )
        last_evaluation = _error_evaluation(brief, iteration, message)
        _save(
            ticket_id,
            brief,
            draft_content=last_draft,
            evaluation=last_evaluation,
            iteration=iteration,
            section_status="needs_human_review",
            approval_status="pending",
            needs_human_review=True,
        )
        return DepartmentOutcome(
            department_id=brief.department_id,
            draft_content=last_draft,
            evaluation=last_evaluation,
            needs_human_review=True,
        )

    assert last_evaluation is not None
    _save(
        ticket_id,
        brief,
        draft_content=last_draft,
        evaluation=last_evaluation,
        iteration=int(last_evaluation["iterations"]),
        section_status="needs_human_review",
        approval_status="pending",
        needs_human_review=True,
    )
    return DepartmentOutcome(
        department_id=brief.department_id,
        draft_content=last_draft,
        evaluation=last_evaluation,
        needs_human_review=True,
    )
