"""LangGraph support-agent flow built on the shared TrackFlow RAG functions."""

from __future__ import annotations

import re
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from data.pipelines import mcp_tools, rag, support_utils

_INCIDENT_KEYWORDS = re.compile(r"\b(incident|ticket|case)\b", re.IGNORECASE)
_JAILBREAK_PATTERNS = (
    re.compile(
        r"\b(ignore|disregard|forget|override|bypass|delete|drop)\b"
        r".{0,60}\b(your|the|all|previous|prior|above|earlier|system|developer)\b"
        r".{0,35}\b(instructions?|rules?|prompts?|guidelines?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(act as|pretend to be|behave as)\b.{0,50}\b(no rules|unrestricted|"
        r"without restrictions|without limits|rule[- ]free)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(reveal|print|show|repeat)\b.{0,35}\b(system|developer)\s+prompt\b", re.IGNORECASE),
)
_OUT_OF_SCOPE_TASKS = re.compile(
    r"\b(essay|homework|school assignment|class assignment|coding|programming|"
    r"write (me )?a (story|poem|song|resume)|relationship advice|medical advice|"
    r"legal advice|financial advice|personal advice)\b",
    re.IGNORECASE,
)
_TRACKFLOW_TOPICS = re.compile(
    r"\b(trackflow|shipment|shipping|tracking|order|track (my |the )?(package|parcel|order)|"
    r"package|parcel|delivery|deliveries|return|returns|refund|sla|service level|"
    r"incident|ticket|case|lost (package|parcel|shipment)|failed delivery|wrong address|"
    r"address change|courier|logistics|dispatch)\b",
    re.IGNORECASE,
)
_GUARDRAIL_REDIRECT = (
    "I can help with TrackFlow logistics support, including shipment tracking, returns, "
    "SLA policies, and delivery incidents. Please ask a question about one of those topics."
)


class SupportAgentState(TypedDict):
    """State and auditable node outputs for a single support-agent run."""

    question: str
    retrieved_context: list[dict[str, Any]]
    answer: str
    error: str | None
    trace: list[dict[str, Any]]
    intent: str | None
    incident_id: str | None
    incident_result: dict[str, Any] | None
    guardrail_reason: str | None


_INVALID_QUESTION = "Please provide a non-empty question."
_SAFE_ERROR = "The support agent could not complete this request. Please try again later."
_INCIDENT_FALLBACKS = {
    "not_found": "I could not find a matching incident in the incident manager. Please double-check the incident ID.",
    "timeout": "The incident manager did not respond in time. Please try again shortly.",
    "unavailable": "I was unable to reach the incident manager right now. Please try again later.",
    "authentication": "I could not verify access to the incident manager right now. Please try again later.",
    "authorization": "I do not have permission to look up that incident right now. Please try again later.",
    "error": "I was unable to reach the incident manager right now. Please try again later.",
}


def _trace_entry(
    state: SupportAgentState,
    node: str,
    output: dict[str, Any],
) -> list[dict[str, Any]]:
    """Append an ordered, inspectable record of the node's produced values."""
    return [*state.get("trace", []), {"node": node, "order": len(state.get("trace", [])) + 1, "output": output}]


def _classify_intent(question: str) -> str:
    """Decide whether a question needs the live incident tool or RAG policy lookup."""
    if support_utils.extract_incident_id(question) or _INCIDENT_KEYWORDS.search(question):
        return "incident"
    return "policy"


def _jailbreak_attempt(question: str) -> bool:
    """Recognize common instruction-override attempts without an LLM call."""
    return any(pattern.search(question) for pattern in _JAILBREAK_PATTERNS)


def _scope_guardrail(question: str) -> bool:
    """Allow TrackFlow logistics topics and reject personal or unrelated requests."""
    if _OUT_OF_SCOPE_TASKS.search(question):
        return True
    return not _TRACKFLOW_TOPICS.search(question)


def validate_question(state: SupportAgentState) -> dict[str, Any]:
    """Normalize input and deterministically check security and support scope."""
    question = state.get("question", "").strip()
    error = None if question else _INVALID_QUESTION
    guardrail_reason = None
    if question and _jailbreak_attempt(question):
        guardrail_reason = "jailbreak"
    elif question and _scope_guardrail(question):
        guardrail_reason = "out_of_scope"
    intent = _classify_intent(question) if question and not guardrail_reason else None
    incident_id = support_utils.extract_incident_id(question) if question else None
    output = {
        "valid": error is None,
        "question": question,
        "error": error,
        "intent": intent,
        "incident_id": incident_id,
        "guardrail_reason": guardrail_reason,
    }
    return {
        "question": question,
        "error": error,
        "intent": intent,
        "incident_id": incident_id,
        "guardrail_reason": guardrail_reason,
        "trace": _trace_entry(state, "validate_question", output),
    }


def guardrail_refusal(state: SupportAgentState) -> dict[str, Any]:
    """Stop unsafe or out-of-scope input and redirect to TrackFlow support."""
    reason = state.get("guardrail_reason") or "out_of_scope"
    output = {"answer": _GUARDRAIL_REDIRECT, "reason": reason}
    return {
        "answer": _GUARDRAIL_REDIRECT,
        "trace": _trace_entry(state, "guardrail_refusal", output),
    }


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


def lookup_ticket(state: SupportAgentState) -> dict[str, Any]:
    """Call the MCP `get_incident` tool — the only path to incident data."""
    incident_id = state.get("incident_id")
    if not incident_id:
        result = {
            "found": False,
            "incident_id": None,
            "status": None,
            "category": None,
            "origin": None,
            "created_at": None,
            "updated_at": None,
            "error": "not_found",
        }
    else:
        result = mcp_tools.lookup_incident_via_mcp(incident_id)

    outcome = "success" if result["found"] else (result.get("error") or "error")
    output = {"outcome": outcome, "incident": result}
    return {
        "incident_result": result,
        "error": None,
        "trace": _trace_entry(state, "lookup_ticket", output),
    }


def synthesize_ticket_answer(state: SupportAgentState) -> dict[str, Any]:
    """Compose a grounded answer strictly from real incident manager fields."""
    incident = state["incident_result"]
    answer = (
        f"Incident {incident['incident_id']} is currently '{incident['status']}' "
        f"(category: {incident['category']}, origin: {incident['origin']}). "
        f"Created {incident['created_at']}, last updated {incident['updated_at']}."
    )
    output = {"answer": answer}
    return {
        "answer": answer,
        "error": None,
        "trace": _trace_entry(state, "synthesize_ticket_answer", output),
    }


def incident_fallback(state: SupportAgentState) -> dict[str, Any]:
    """Return an honest fallback — never invent ticket status, category, or dates."""
    incident = state.get("incident_result") or {}
    outcome = incident.get("error") or "error"
    answer = _INCIDENT_FALLBACKS.get(outcome, _INCIDENT_FALLBACKS["error"])
    output = {"answer": answer, "outcome": outcome}
    return {"answer": answer, "trace": _trace_entry(state, "incident_fallback", output)}


def route_intent(state: SupportAgentState) -> str:
    """Router decision: guardrail, incident tool, RAG retrieval, or error handling."""
    if state.get("guardrail_reason"):
        return "guardrail_refusal"
    if state.get("error"):
        return "handle_error"
    return "lookup_ticket" if state.get("intent") == "incident" else "retrieve_context"


def _after_retrieval(state: SupportAgentState) -> str:
    if state.get("error"):
        return "handle_error"
    return "generate_answer" if state.get("retrieved_context") else "safe_fallback"


def _after_generation(state: SupportAgentState) -> str:
    return "handle_error" if state.get("error") else END


def _after_lookup(state: SupportAgentState) -> str:
    incident = state.get("incident_result") or {}
    return "synthesize_ticket_answer" if incident.get("found") else "incident_fallback"


def _build_graph():
    builder = StateGraph(SupportAgentState)
    builder.add_node("validate_question", validate_question)
    builder.add_node("guardrail_refusal", guardrail_refusal)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("generate_answer", generate_answer)
    builder.add_node("safe_fallback", safe_fallback)
    builder.add_node("handle_error", handle_error)
    builder.add_node("lookup_ticket", lookup_ticket)
    builder.add_node("synthesize_ticket_answer", synthesize_ticket_answer)
    builder.add_node("incident_fallback", incident_fallback)

    builder.add_edge(START, "validate_question")
    builder.add_conditional_edges(
        "validate_question",
        route_intent,
        {
            "retrieve_context": "retrieve_context",
            "lookup_ticket": "lookup_ticket",
            "handle_error": "handle_error",
            "guardrail_refusal": "guardrail_refusal",
        },
    )
    builder.add_edge("guardrail_refusal", END)
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
    builder.add_conditional_edges(
        "lookup_ticket",
        _after_lookup,
        {
            "synthesize_ticket_answer": "synthesize_ticket_answer",
            "incident_fallback": "incident_fallback",
        },
    )
    builder.add_edge("synthesize_ticket_answer", END)
    builder.add_edge("incident_fallback", END)
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
            "intent": None,
            "incident_id": None,
            "incident_result": None,
            "guardrail_reason": None,
        },
        config=config,
    )
    return {**result, "thread_id": run_id}


def get_support_agent_checkpoint(thread_id: str) -> dict[str, Any] | None:
    """Read the latest persisted graph state for a prior run ID."""
    checkpoint = support_agent_graph.get_state({"configurable": {"thread_id": thread_id}})
    return dict(checkpoint.values) if checkpoint.values else None
