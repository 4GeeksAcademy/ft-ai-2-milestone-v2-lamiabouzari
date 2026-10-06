"""RFP intake pipeline: convert, classify, orchestrate, work, synthesize.

Part 1 statuses are only analyzing → intake_complete, or analyzing → discarded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from data.pipelines.rfp_intake.classifier import classify
from data.pipelines.rfp_intake.convert import UnreadablePdf, pdf_to_markdown
from data.pipelines.rfp_intake.extract import extract_metadata
from data.pipelines.rfp_intake.orchestrator import plan
from data.pipelines.rfp_intake.store import (
    HANDOFF_CONTRACT,
    mark_discarded,
    mark_intake_complete,
    record_error,
    replace_sections,
    save_markdown,
    save_metadata,
    save_synthesizer,
)
from data.pipelines.rfp_intake.synthesizer import synthesize
from data.pipelines.rfp_intake.workers import analyze, relevant_extract


def _metadata_values(metadata, classification) -> dict[str, Any]:
    return {
        "client_name": metadata.client_name,
        "client_country": metadata.client_country,
        "services_requested": list(metadata.services_requested),
        "monthly_volume": metadata.monthly_volume,
        "deadline": metadata.deadline,
        "budget_range": metadata.budget_range,
        "departments_needed": list(metadata.departments_needed),
        "currency_context": metadata.currency_context,
        "readability": dict(metadata.readability),
        "is_rfp": classification.is_rfp,
        "document_style": classification.document_style,
        "classification_reason": classification.reason,
    }


def run_markdown(ticket_id: str, markdown: str) -> dict[str, Any]:
    """Run every agent step on Markdown that was already converted from the PDF."""
    save_markdown(ticket_id, markdown)
    metadata = extract_metadata(markdown)
    classification = classify(markdown)
    if not classification.is_rfp:
        metadata.departments_needed = []
        save_metadata(ticket_id, _metadata_values(metadata, classification))
        replace_sections(ticket_id, [])
        mark_discarded(ticket_id, classification.reason)
        return {"ticket_id": ticket_id, "status": "discarded", "workers_ran": False}

    orchestrated = plan(metadata, markdown)
    metadata.departments_needed = [item.department_key for item in orchestrated.departments]
    metadata.currency_context = orchestrated.currency_context
    save_metadata(ticket_id, _metadata_values(metadata, classification))

    worker_results = []
    section_rows = []
    for workstream in orchestrated.departments:
        extract = relevant_extract(markdown, workstream.department_key)
        result = analyze(workstream.department_key, metadata, extract)
        worker_results.append(result)
        section_rows.append(
            {
                "department_key": result.department_key,
                "department_name": result.department_name,
                "contact": result.contact,
                "key_aspects": list(result.key_aspects),
                "open_questions": list(result.open_questions),
                "extract_text": extract,
            }
        )
    replace_sections(ticket_id, section_rows)
    synthesis = synthesize(metadata, worker_results)
    handoff = {
        "contract": HANDOFF_CONTRACT,
        "ticket_id": ticket_id,
        "ready_for_part2": True,
        "currency_context": orchestrated.currency_context,
        "synthesizer": synthesis.model_dump(),
        "sections": [result.model_dump() for result in worker_results],
    }
    save_synthesizer(ticket_id, synthesis.sales_summary, handoff)
    mark_intake_complete(
        ticket_id,
        currency_context=orchestrated.currency_context,
        handoff=handoff,
    )
    return {"ticket_id": ticket_id, "status": "intake_complete", "workers_ran": True}


def process_ticket(ticket_id: str) -> dict[str, Any]:
    """Convert the ticket PDF, then run intake. Conversion happens before agents."""
    from data.pipelines.rfp_intake.store import get_ticket

    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise KeyError(ticket_id)
    if ticket.status != "analyzing":
        return {"ticket_id": ticket_id, "status": ticket.status, "workers_ran": False}
    try:
        markdown = pdf_to_markdown(Path(ticket.pdf_path))
        return run_markdown(ticket_id, markdown)
    except UnreadablePdf as exc:
        mark_discarded(ticket_id, str(exc))
        return {"ticket_id": ticket_id, "status": "discarded", "workers_ran": False}
    except Exception as exc:
        record_error(ticket_id, str(exc))
        return {
            "ticket_id": ticket_id,
            "status": "analyzing",
            "workers_ran": False,
            "intake_failed": True,
        }
