"""LangGraph support-agent flow built on the shared TrackFlow RAG functions.

Input checks, external-content isolation, output checks, and country-policy
enforcement run in this graph. Retrieved documents and MCP payloads stay data.
"""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from data.pipelines import agent_memory, guardrails, mcp_tools, rag, support_utils

logger = logging.getLogger(__name__)

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
    r"address change|courier|carriers|carrier|logistics|dispatch)\b",
    re.IGNORECASE,
)
_GUARDRAIL_REDIRECT = (
    "I can help with TrackFlow logistics support, including shipment tracking, returns, "
    "SLA policies, and delivery incidents. Please ask a question about one of those topics."
)
_UNAUTHORIZED_ORDER = (
    "You are not authorized to view that order. I can only discuss orders that belong "
    "to your authenticated session, and I can't share any details for this request."
)
_GUARDRAIL_EVENTS = {
    "jailbreak": ("input_jailbreak", "block", "security"),
    "out_of_scope": ("input_scope", "redirect", "content"),
    "unauthorized_order": ("order_authorization", "block", "security"),
}

_SESSION: ContextVar[guardrails.SupportSession | None] = ContextVar("trackflow_support_session", default=None)
_TOKEN_SINK: ContextVar[Any] = ContextVar("first_line_cx_token_sink", default=None)
_CANCEL: ContextVar[Any] = ContextVar("first_line_cx_cancel", default=None)


def bind_token_stream(sink: Any, cancel: Any) -> tuple[Any, Any]:
    """Attach a chat transport on the worker that is running the graph.

    POST /agent/query leaves both context vars unset, so that path still uses
    the non-streaming RAG call.
    """
    return _TOKEN_SINK.set(sink), _CANCEL.set(cancel)


def unbind_token_stream(tokens: tuple[Any, Any]) -> None:
    _TOKEN_SINK.reset(tokens[0])
    _CANCEL.reset(tokens[1])


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
    country_enforcement: dict[str, str] | None
    guardrail_events: list[dict[str, Any]]


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


def _log_agent_decision(result: dict[str, Any]) -> None:
    """Record one support turn without the question text or customer address."""
    trace = result.get("trace") or []
    node = "none"
    guardrail = "none"
    if trace and isinstance(trace[-1], dict):
        node = str(trace[-1].get("node") or "none")
    for entry in trace:
        if not isinstance(entry, dict):
            continue
        output = entry.get("output") or {}
        if not isinstance(output, dict):
            continue
        reason = output.get("guardrail_reason") or output.get("reason")
        if reason:
            guardrail = str(reason)
    if guardrail != "none":
        outcome = "refused"
    elif result.get("error"):
        outcome = "error"
    else:
        outcome = "completed"
    logger.info(
        "agent_decision action=support_turn node=%s outcome=%s guardrail=%s",
        node,
        outcome,
        guardrail,
    )


def _trace_entry(
    state: SupportAgentState,
    node: str,
    output: dict[str, Any],
) -> list[dict[str, Any]]:
    """Append an ordered, inspectable record of the node's produced values."""
    return [*state.get("trace", []), {"node": node, "order": len(state.get("trace", [])) + 1, "output": output}]


def _owned_order_ids() -> frozenset[str]:
    session = _SESSION.get()
    if session is None:
        return frozenset()
    return frozenset(str(order_id) for order_id in session.owned_order_ids)


def _order_is_authorized(order_id: str) -> bool:
    """Fail closed. Denial does not surface order fields from the decision."""
    session = _SESSION.get()
    try:
        decision = mcp_tools.authorize_order_access(
            order_id,
            subject=None if session is None else session.subject,
            owned_order_ids=_owned_order_ids(),
        )
    except Exception:
        return False
    return bool(decision.get("authorized")) and decision.get("error") is None


def _append_guardrail_event(
    state: SupportAgentState,
    event: dict[str, str] | None,
) -> list[dict[str, Any]]:
    events = list(state.get("guardrail_events") or [])
    if event is not None:
        events.append(event)
    return events


def _guarded_answer(state: SupportAgentState, answer: str) -> tuple[str, dict[str, str] | None, list[dict[str, Any]]]:
    safe_answer, event = guardrails.apply_output_guardrail(answer, owned_order_ids=_owned_order_ids())
    return safe_answer, event, _append_guardrail_event(state, event)


def _with_operational_memory(question: str, answer: str) -> str:
    """Append saved operational facts that match this question. Memory stays data."""
    note = agent_memory.operational_context(question)
    if not note or note in answer:
        return answer
    return f"{answer.rstrip()}\n\nOperational memory: {note}"


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
    order_id = guardrails.extract_order_id(question) if question else None
    if question and order_id and not _order_is_authorized(order_id):
        guardrail_reason = "unauthorized_order"
    elif question and _jailbreak_attempt(question):
        guardrail_reason = "jailbreak"
    elif question and _scope_guardrail(question) and not agent_memory.allows_operational_update(question):
        guardrail_reason = "out_of_scope"
    country_enforcement = None
    if question and error is None and guardrail_reason is None:
        country_enforcement = guardrails.detect_country_policy_conflict(question)
    intent = (
        _classify_intent(question)
        if question and not guardrail_reason and country_enforcement is None
        else None
    )
    incident_id = support_utils.extract_incident_id(question) if question else None
    output = {
        "valid": error is None,
        "question": question,
        "error": error,
        "intent": intent,
        "incident_id": incident_id,
        "guardrail_reason": guardrail_reason,
        "country_enforcement": country_enforcement,
    }
    return {
        "question": question,
        "error": error,
        "intent": intent,
        "incident_id": incident_id,
        "guardrail_reason": guardrail_reason,
        "country_enforcement": country_enforcement,
        "trace": _trace_entry(state, "validate_question", output),
    }


def guardrail_refusal(state: SupportAgentState) -> dict[str, Any]:
    """Stop unsafe or out-of-scope input and redirect to TrackFlow support."""
    reason = state.get("guardrail_reason") or "out_of_scope"
    guardrail_name, action, failure_type = _GUARDRAIL_EVENTS.get(reason, ("input_scope", "redirect", "content"))
    event = guardrails.record_guardrail(guardrail_name, action, failure_type)
    answer = _UNAUTHORIZED_ORDER if reason == "unauthorized_order" else _GUARDRAIL_REDIRECT
    output = {
        "answer": answer,
        "reason": reason,
        "guardrail": event["guardrail"],
        "action": event["action"],
        "failure_type": event["failure_type"],
    }
    return {
        "answer": answer,
        "guardrail_events": _append_guardrail_event(state, event),
        "trace": _trace_entry(state, "guardrail_refusal", output),
    }


def enforce_country_policy(state: SupportAgentState) -> dict[str, Any]:
    """Reject a cross-country policy switch and answer with the order's country only."""
    decision = state.get("country_enforcement") or {}
    answer = guardrails.country_policy_answer(
        actual_country=decision["actual_country"],
        requested_country=decision["requested_country"],
        place=decision["place"],
    )
    answer, output_event, events = _guarded_answer(state, answer)
    if output_event is None:
        event = guardrails.record_guardrail("country_policy", "redirect", "content")
        events = _append_guardrail_event(state, event)
    else:
        event = output_event
    output = {
        "answer": answer,
        "guardrail": event["guardrail"],
        "action": event["action"],
        "failure_type": event["failure_type"],
        "actual_country": decision.get("actual_country"),
        "requested_country": decision.get("requested_country"),
    }
    return {
        "answer": answer,
        "guardrail_events": events,
        "trace": _trace_entry(state, "enforce_country_policy", output),
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

    context, injected = guardrails.isolate_documents(context)
    output: dict[str, Any] = {"retrieved_context": context, "result_count": len(context)}
    events = list(state.get("guardrail_events") or [])
    if injected:
        event = guardrails.record_guardrail("external_content", "quarantine", "structural")
        output.update(event)
        events = _append_guardrail_event(state, event)
    return {
        "retrieved_context": context,
        "error": None,
        "guardrail_events": events,
        "trace": _trace_entry(state, "retrieve_context", output),
    }


def _streamed_rag_answer(question: str, context: list[dict[str, Any]], sink: Any, cancel: Any) -> str:
    """Forward model deltas as they arrive, then apply the existing safeguards."""
    if not context:
        return rag.SAFE_REFUSAL
    parts: list[str] = []
    for delta in rag.iter_model_deltas(question, context):
        if cancel is not None and cancel.is_set():
            break
        parts.append(delta)
        sink(delta)
    raw = "".join(parts).strip() or rag.SAFE_REFUSAL
    return rag._apply_business_safeguards(question, raw, context)


def generate_answer(state: SupportAgentState) -> dict[str, Any]:
    """Generate a grounded response using the existing RAG answer function."""
    try:
        sink = _TOKEN_SINK.get()
        if sink is None:
            answer = rag.generate_answer(state["question"], state["retrieved_context"])
        else:
            answer = _streamed_rag_answer(state["question"], state["retrieved_context"], sink, _CANCEL.get())
    except Exception:
        error = "Unable to generate a TrackFlow response. Please try again later."
        output = {"error": error}
        return {"answer": rag.SAFE_REFUSAL, "error": error, "trace": _trace_entry(state, "generate_answer", output)}

    answer = _with_operational_memory(state.get("question", ""), answer)
    answer, event, events = _guarded_answer(state, answer)
    output = {"answer": answer}
    if event is not None:
        output.update(event)
    return {
        "answer": answer,
        "error": None,
        "guardrail_events": events,
        "trace": _trace_entry(state, "generate_answer", output),
    }


def safe_fallback(state: SupportAgentState) -> dict[str, Any]:
    """Return the RAG safe refusal when evidence is absent or a step failed."""
    error = state.get("error")
    answer = _with_operational_memory(state.get("question", ""), rag.SAFE_REFUSAL)
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

    result, injected = guardrails.isolate_tool_result(result)
    outcome = "success" if result["found"] else (result.get("error") or "error")
    output: dict[str, Any] = {"outcome": outcome, "incident": result}
    events = list(state.get("guardrail_events") or [])
    if injected:
        event = guardrails.record_guardrail("external_content", "quarantine", "structural")
        output.update(event)
        events = _append_guardrail_event(state, event)
    return {
        "incident_result": result,
        "error": None,
        "guardrail_events": events,
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
    answer, event, events = _guarded_answer(state, answer)
    output = {"answer": answer}
    if event is not None:
        output.update(event)
    return {
        "answer": answer,
        "error": None,
        "guardrail_events": events,
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
    if state.get("country_enforcement"):
        return "enforce_country_policy"
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
    builder.add_node("enforce_country_policy", enforce_country_policy)
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
            "enforce_country_policy": "enforce_country_policy",
        },
    )
    builder.add_edge("guardrail_refusal", END)
    builder.add_edge("enforce_country_policy", END)
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


def run_support_agent(
    question: str,
    *,
    thread_id: str | None = None,
    session: guardrails.SupportSession | None = None,
) -> dict[str, Any]:
    """Invoke the compiled graph and return state, trace, and checkpoint ID."""
    run_id = thread_id or str(uuid4())
    config = {"configurable": {"thread_id": run_id}}
    resolution = None
    question_for_graph = question
    try:
        prepared = agent_memory.prepare_confirmation(question, run_id)
    except Exception:
        prepared = None
    if prepared is not None:
        resolution = prepared.get("memory_resolution")
        if prepared.get("skip_graph"):
            result = {**prepared["result"], "thread_id": run_id}
            _log_agent_decision(result)
            return result
        question_for_graph = str(prepared.get("question") or question)
    token = _SESSION.set(session)
    try:
        result = support_agent_graph.invoke(
            {
                "question": question_for_graph,
                "retrieved_context": [],
                "answer": "",
                "error": None,
                "trace": [],
                "intent": None,
                "incident_id": None,
                "incident_result": None,
                "guardrail_reason": None,
                "country_enforcement": None,
                "guardrail_events": [],
            },
            config=config,
        )
    finally:
        _SESSION.reset(token)
    try:
        if resolution is None:
            result = agent_memory.attach_proposal(result, question_for_graph, run_id)
        else:
            result = {**result, "memory_proposal": None}
    except Exception:
        result = {**result, "memory_proposal": None}
    if resolution is not None:
        result["memory_resolution"] = resolution
    result = {**result, "thread_id": run_id}
    _log_agent_decision(result)
    return result


def get_support_agent_checkpoint(thread_id: str) -> dict[str, Any] | None:
    """Read the latest persisted graph state for a prior run ID."""
    checkpoint = support_agent_graph.get_state({"configurable": {"thread_id": thread_id}})
    return dict(checkpoint.values) if checkpoint.values else None
