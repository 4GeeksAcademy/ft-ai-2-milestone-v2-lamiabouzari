"""Structured-output boundary for the intake agents.

The default backend executes the agent contracts locally so intake does not
call a live model. Set RFP_INTAKE_LLM=1 to use the same OpenAI-compatible
gateway as the RAG pipeline. Either backend must return the agent schema.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

from data.pipelines.rfp_intake.classifier import SYSTEM_PROMPT as CLASSIFIER_PROMPT
from data.pipelines.rfp_intake.orchestrator import SYSTEM_PROMPT as ORCHESTRATOR_PROMPT
from data.pipelines.rfp_intake.synthesizer import SYSTEM_PROMPT as SYNTHESIZER_PROMPT
from data.pipelines.rfp_intake.workers import SYSTEM_PROMPT as WORKER_PROMPT

SchemaT = TypeVar("SchemaT", bound=BaseModel)

Backend = Callable[[str, dict[str, Any]], dict[str, Any]]

_backend: Backend | None = None

_PROMPTS = {
    "classify": CLASSIFIER_PROMPT,
    "orchestrate": ORCHESTRATOR_PROMPT,
    "work": WORKER_PROMPT,
    "synthesize": SYNTHESIZER_PROMPT,
}


def set_backend(backend: Backend | None) -> None:
    """Replace the structured-output backend. None restores the default."""
    global _backend
    _backend = backend


def grounded(task: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Offline executor for the four agent contracts."""
    if task == "classify":
        from data.pipelines.rfp_intake.classifier import decide

        return decide(str(payload.get("markdown") or "")).model_dump()
    if task == "orchestrate":
        from data.pipelines.rfp_intake.orchestrator import decide
        from data.pipelines.rfp_intake.schemas import RfpMetadataDraft

        metadata = RfpMetadataDraft.model_validate(payload.get("metadata") or {})
        return decide(metadata, str(payload.get("markdown") or "")).model_dump()
    if task == "work":
        from data.pipelines.rfp_intake.schemas import RfpMetadataDraft
        from data.pipelines.rfp_intake.workers import decide

        metadata = RfpMetadataDraft.model_validate(payload.get("metadata") or {})
        return decide(
            str(payload.get("department_key") or ""),
            metadata,
            str(payload.get("extract") or ""),
        ).model_dump()
    if task == "synthesize":
        from data.pipelines.rfp_intake.schemas import RfpMetadataDraft, WorkerResult
        from data.pipelines.rfp_intake.synthesizer import decide

        metadata = RfpMetadataDraft.model_validate(payload.get("metadata") or {})
        workers = [WorkerResult.model_validate(item) for item in payload.get("workers") or []]
        return decide(metadata, workers).model_dump()
    raise ValueError(f"Unknown intake task: {task}")


def openai_complete(task: str, payload: dict[str, Any], schema: type[BaseModel]) -> dict[str, Any]:
    """Call the OpenAI-compatible gateway and parse a JSON object."""
    from openai import OpenAI

    model = os.getenv(
        "RFP_INTAKE_MODEL",
        os.getenv("RAG_GENERATION_MODEL", "downtown-miami/openrouter/openai/gpt-6-luna"),
    )
    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _PROMPTS[task]},
            {
                "role": "user",
                "content": (
                    "JSON schema:\n"
                    + json.dumps(schema.model_json_schema())
                    + "\n\nInput:\n"
                    + json.dumps(payload)
                ),
            },
        ],
    )
    content = response.choices[0].message.content or "{}"
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Intake model did not return a JSON object.")
    return parsed


def complete(task: str, payload: dict[str, Any], schema: type[SchemaT]) -> SchemaT:
    """Run one agent task and validate the structured result."""
    if _backend is not None:
        raw = _backend(task, payload)
    elif os.getenv("RFP_INTAKE_LLM") == "1":
        raw = openai_complete(task, payload, schema)
    else:
        raw = grounded(task, payload)
    return schema.model_validate(raw)
