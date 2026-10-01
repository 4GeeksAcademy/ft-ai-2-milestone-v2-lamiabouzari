"""Public-facing TrackFlow knowledge-base query endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from data.pipelines.rag import query

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class KnowledgeQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class KnowledgeQueryResponse(BaseModel):
    answer: str


@router.post("/query", response_model=KnowledgeQueryResponse)
def knowledge_query(request: KnowledgeQueryRequest) -> KnowledgeQueryResponse:
    """Return a generated answer only; retrieval details remain internal."""
    return KnowledgeQueryResponse(answer=query(request.question.strip()))
