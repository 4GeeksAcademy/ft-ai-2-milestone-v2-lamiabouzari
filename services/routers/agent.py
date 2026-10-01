"""API routes for the LangGraph TrackFlow support agent."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from data.pipelines.support_agent import run_support_agent

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentQueryRequest(BaseModel):
    question: str = Field(max_length=2000)


class AgentQueryResponse(BaseModel):
    answer: str
    error: str | None = None
    trace: list[dict[str, Any]]
    thread_id: str


@router.post("/query", response_model=AgentQueryResponse)
def agent_query(request: AgentQueryRequest) -> AgentQueryResponse:
    """Invoke the agent graph and return its answer and execution trace."""
    try:
        result = run_support_agent(request.question)
    except Exception as exc:
        # Do not leak framework or provider details to API clients.
        raise HTTPException(
            status_code=500,
            detail="The support agent could not complete this request.",
        ) from exc

    if result.get("error") == "Please provide a non-empty question.":
        raise HTTPException(status_code=422, detail=result["error"])

    return AgentQueryResponse(
        answer=result["answer"],
        error=result.get("error"),
        trace=result["trace"],
        thread_id=result["thread_id"],
    )
