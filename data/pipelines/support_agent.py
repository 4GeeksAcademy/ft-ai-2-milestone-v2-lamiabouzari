"""LangGraph support-agent flow built on the shared TrackFlow RAG functions."""

from __future__ import annotations

from typing import Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from data.pipelines import rag


class SupportAgentState(TypedDict):
    """State and auditable node outputs for a single support-agent run."""

    question: str
    retrieved_context: list[dict[str, Any]]
    answer: str
    error: str | None
    trace: list[dict[str, Any]]


_INVALID_QUESTION = "Please provide a non-empty question."
_SAFE_ERROR = "The support agent could not complete this request. Please try again later."


def _trace_entry(
    state: SupportAgentState,
    node: str,
    output: dict[str, Any],
) -> list[dict[str, Any]]:
    """Append an ordered, inspectable record of the node's produced values."""
    return [*state.get("trace", []), {"node": node, "order": len(state.get("trace", [])) + 1, "output": output}]


def validate_question(state: SupportAgentState) -> dict[str, Any]:
    """Normalize the incoming question and stop blank inputs before retrieval."""
    question = state.get("question", "").strip()
    error = None if question else _INVALID_QUESTION
    output = {"valid": error is None, "question": question, "error": error}
    return {"question": question, "error": error, "trace": _trace_entry(state, "validate_question", output)}


def retrieve_context(state: SupportAgentState) -> dict[str, Any]:
    """Retrieve evidence through the existing RAG retrieval function."""
    try:
        context = rag.retrieve(state["question"])
    except Exception:
        error = "Unable to retrieve TrackFlow information. Please try again later."
        output = {"error": error}
        return {
            "retrieved_context": [],
            "error": error,
            "trace": _trace_entry(state, "retrieve_context", output),
        }

    output = {"retrieved_context": context, "result_count": len(context)}
    return {
        "retrieved_context": context,
        "error": None,
        "trace": _trace_entry(state, "retrieve_context", output),
    }


def generate_answer(state: SupportAgentState) -> dict[str, Any]:
    """Generate a grounded response using the existing RAG answer function."""
    try:
        answer = rag.generate_answer(state["question"], state["retrieved_context"])
    except Exception:
        error = "Unable to generate a TrackFlow response. Please try again later."
        output = {"error": error}
        return {"answer": rag.SAFE_REFUSAL, "error": error, "trace": _trace_entry(state, "generate_answer", output)}

    output = {"answer": answer}
    return {"answer": answer, "error": None, "trace": _trace_entry(state, "generate_answer", output)}


def safe_fallback(state: SupportAgentState) -> dict[str, Any]:
    """Return the RAG safe refusal when evidence is absent or a step failed."""
    error = state.get("error")
    answer = rag.SAFE_REFUSAL
    output = {"answer": answer, "error": error}
    return {"answer": answer, "trace": _trace_entry(state, "safe_fallback", output)}


def handle_error(state: SupportAgentState) -> dict[str, Any]:
    """Record a failed graph step and return a safe, non-sensitive response."""
    error = state.get("error") or _SAFE_ERROR
    answer = rag.SAFE_REFUSAL
    output = {"answer": answer, "error": error}
    return {"answer": answer, "trace": _trace_entry(state, "handle_error", output)}


def _after_validation(state: SupportAgentState) -> str:
    return "handle_error" if state.get("error") else "retrieve_context"


def _after_retrieval(state: SupportAgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "generate_answer" if state.get("retrieved_context") else "safe_fallback"


def _after_generation(state: SupportAgentState) -> str:
    return "handle_error" if state.get("error") else END


def _build_graph():
    builder = StateGraph(SupportAgentState)
    builder.add_node("validate_question", validate_question)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("generate_answer", generate_answer)
    builder.add_node("safe_fallback", safe_fallback)
    builder.add_node("handle_error", handle_error)

    builder.add_edge(START, "validate_question")
    builder.add_conditional_edges(
        "validate_question",
        _after_validation,
        {"retrieve_context": "retrieve_context", "handle_error": "handle_error"},
    )
    builder.add_conditional_edges(
        "retrieve_context",
        _after_retrieval,
        {
            "generate_answer": "generate_answer",
            "safe_fallback": "safe_fallback",
            "handle_error": "handle_error",
        },
    )
    builder.add_conditional_edges(
        "generate_answer",
        _after_generation,
        {"handle_error": "handle_error", END: END},
    )
    builder.add_edge("safe_fallback", END)
    builder.add_edge("handle_error", END)
    return builder.compile(checkpointer=MemorySaver())


# Compile once at import time; all invocations use the checkpointed graph.
support_agent_graph = _build_graph()


def run_support_agent(question: str, *, thread_id: str | None = None) -> dict[str, Any]:
    """Invoke the compiled graph and return state, trace, and checkpoint ID."""
    run_id = thread_id or str(uuid4())
    config = {"configurable": {"thread_id": run_id}}
    result = support_agent_graph.invoke(
        {
            "question": question,
            "retrieved_context": [],
            "answer": "",
            "error": None,
            "trace": [],
        },
        config=config,
    )
    return {**result, "thread_id": run_id}


def get_support_agent_checkpoint(thread_id: str) -> dict[str, Any] | None:
    """Read the latest persisted graph state for a prior run ID."""
    checkpoint = support_agent_graph.get_state({"configurable": {"thread_id": thread_id}})
    return dict(checkpoint.values) if checkpoint.values else None
