"""Seed a Part 2 ticket so Part 3 tests do not reimplement intake."""

from __future__ import annotations

from sqlmodel import Session

from data.pipelines.rfp_intake import store
from data.pipelines.rfp_intake.departments import DEPARTMENTS
from models.rfp import RfpTicket

EVALUATION = {
    "department_id": "warehouse",
    "readability": {"pass": True, "score": 70, "details": {}},
    "relevance": {"pass": True, "missing_aspects": []},
    "compliance": {"pass": True, "rule_ids": [], "violations": []},
    "overall_pass": True,
    "feedback_for_generator": "All readability, relevance, and compliance checks passed.",
    "iterations": 1,
}

DEFAULT_ASPECTS = [
    "Store apparel orders in Zaragoza.",
    "On-time delivery SLA: 97%.",
]


def seed_part2_ticket(
    *,
    departments: list[str],
    drafts: dict[str, str],
    status: str = "under_evaluation",
    country: str = "Spain",
    currency: str = "EUR",
    aspects: dict[str, list[str]] | None = None,
) -> str:
    ticket = store.create_ticket(source_filename="client.pdf", pdf_path="missing-rfp.pdf")
    store.save_metadata(
        ticket.id,
        {
            "client_name": "ModaViva",
            "client_country": country,
            "services_requested": ["warehousing"],
            "monthly_volume": "12,000 orders",
            "deadline": None,
            "budget_range": None,
            "departments_needed": departments,
            "currency_context": currency,
            "readability": {"word_count": 40},
            "is_rfp": True,
            "document_style": "formal",
            "classification_reason": "seeded part 2 handoff",
        },
    )
    section_rows = []
    routing_sections = []
    part3_departments = []
    asks = []
    for department in departments:
        info = DEPARTMENTS[department]
        evaluation = dict(EVALUATION)
        evaluation["department_id"] = department
        key_aspects = (aspects or {}).get(department, list(DEFAULT_ASPECTS))
        questions = ["What deadline should this department use?"]
        section_rows.append(
            {
                "department_key": department,
                "department_name": info["name"],
                "contact": info["contact"],
                "key_aspects": key_aspects,
                "open_questions": questions,
                "extract_text": "",
                "draft_content": drafts[department],
                "evaluation_results": evaluation,
                "iteration_count": 1,
                "section_status": "passed",
                "approval_status": "pending",
                "needs_human_review": status == "needs_human_review",
            }
        )
        routing_sections.append(
            {
                "department_key": department,
                "department_name": info["name"],
                "contact": info["contact"],
                "key_aspects": key_aspects,
                "open_questions": questions,
            }
        )
        part3_departments.append(
            {
                "department_id": department,
                "department_name": info["name"],
                "contact": info["contact"],
                "draft_content": drafts[department],
                "evaluation_result": evaluation,
                "iterations": 1,
                "approval_status": "pending",
                "needs_human_review": status == "needs_human_review",
            }
        )
        asks.append(
            {
                "department_key": department,
                "department_name": info["name"],
                "contact": info["contact"],
                "needs": " ".join(key_aspects),
                "questions": questions,
            }
        )
    store.replace_sections(ticket.id, section_rows)
    routing = {
        "contract": "trackflow.rfp.intake.v1",
        "ticket_id": ticket.id,
        "ready_for_part2": True,
        "currency_context": currency,
        "synthesizer": {
            "sales_summary": f"Sales handoff for ModaViva ({country}, currency {currency}).",
            "department_asks": asks,
        },
        "sections": routing_sections,
    }
    store.mark_intake_complete(ticket.id, currency_context=currency, handoff=routing)
    with Session(store.get_engine(), expire_on_commit=False) as session:
        row = session.get(RfpTicket, ticket.id)
        if row is None:
            raise KeyError(ticket.id)
        row.status = status
        row.part3_handoff_ready = True
        row.part3_handoff = {
            "contract": "trackflow.rfp.response.v1",
            "ticket_id": ticket.id,
            "ready_for_part3": True,
            "departments": part3_departments,
        }
        session.add(row)
        session.commit()
    return ticket.id
