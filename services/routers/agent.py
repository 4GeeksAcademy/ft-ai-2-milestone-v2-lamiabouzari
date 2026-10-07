"""API routes for the LangGraph TrackFlow support agent."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from agent_rate_limit import allow_agent_request
from data.pipelines.support_agent import run_support_agent
from dependencies import get_current_user
from model_input import ModelInputError, normalize_model_question
from models.user import UserPublic

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


class AgentQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        try:
            return normalize_model_question(value)
        except ModelInputError as exc:
            raise ValueError(str(exc)) from exc


class AgentQueryResponse(BaseModel):
    answer: str
    error: str | None = None
    trace: list[dict[str, Any]]
    thread_id: str


@router.post("/query", response_model=AgentQueryResponse)
def agent_query(
    request: AgentQueryRequest,
    _user: UserPublic = Depends(get_current_user),
) -> AgentQueryResponse:
    """Invoke the agent graph and return its answer and execution trace."""
    if not allow_agent_request(str(_user.id)):
        logger.warning("agent_rate_limited action=support_turn outcome=rejected")
        raise HTTPException(status_code=429, detail="Too many agent requests. Try again later.")
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
