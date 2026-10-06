"""Synthesizer agent. Combines worker results for Sales."""

from __future__ import annotations

from data.pipelines.rfp_intake.schemas import DepartmentAsk, RfpMetadataDraft, SynthesizerResult, WorkerResult

SYSTEM_PROMPT = """You are the TrackFlow RFP synthesizer.
Combine the worker results into one Sales-facing summary.
State what each department needs and which named contact Sales should ask.
Do not add departments, volumes, prices, or capacity that the workers did not provide.
Return JSON for a SynthesizerResult."""


def decide(metadata: RfpMetadataDraft, workers: list[WorkerResult]) -> SynthesizerResult:
    """Summarize confirmed scope and who Sales should contact."""
    client = metadata.client_name or "the client"
    country = metadata.client_country or "country not stated"
    lines = [
        (
            f"Sales handoff for {client} ({country}, currency {metadata.currency_context}). "
            "Figures below are only those stated in the RFP."
        )
    ]
    asks: list[DepartmentAsk] = []
    for worker in workers:
        needs = "; ".join(worker.key_aspects) or "No confirmed scope details were stated."
        lines.append(f"{worker.department_name} — {worker.contact} needs: {needs}")
        if worker.open_questions:
            lines.append(
                f"Sales should ask {worker.contact}: " + " ".join(worker.open_questions)
            )
        asks.append(
            DepartmentAsk(
                department_key=worker.department_key,
                department_name=worker.department_name,
                contact=worker.contact,
                needs=needs,
                questions=list(worker.open_questions),
            )
        )
    return SynthesizerResult(sales_summary="\n".join(lines), department_asks=asks)


def synthesize(metadata: RfpMetadataDraft, workers: list[WorkerResult]) -> SynthesizerResult:
    """Run the synthesizer agent and validate its structured output."""
    from data.pipelines.rfp_intake.llm import complete

    return complete(
        "synthesize",
        {
            "metadata": metadata.model_dump(),
            "workers": [worker.model_dump() for worker in workers],
        },
        SynthesizerResult,
    )
