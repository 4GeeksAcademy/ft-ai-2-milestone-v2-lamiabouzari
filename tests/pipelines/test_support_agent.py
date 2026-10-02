from __future__ import annotations

from uuid import uuid4

from data.pipelines import incident_tool, rag, support_agent
from routers import agent


def test_agent_answer_uses_grounded_trackflow_knowledge(monkeypatch):
    evidence = {
        "source_document": "trackflow-returns-policy.en.md",
        "section": "International returns",
        "text": "International returns are not automatic. They require manual handling.",
    }
    seen = {}
    monkeypatch.setattr(rag, "retrieve", lambda question: [evidence])

    def generate(question, context):
        seen["question"] = question
        seen["context"] = context
        return "International returns are not automatic and require manual handling."

    monkeypatch.setattr(rag, "generate_answer", generate)

    result = support_agent.run_support_agent("How are international returns handled?")

    assert result["answer"] == "International returns are not automatic and require manual handling."
    assert seen == {
        "question": "How are international returns handled?",
        "context": [evidence],
    }
    assert "automatic" in evidence["text"]
    assert [entry["node"] for entry in result["trace"]] == [
        "validate_question",
        "retrieve_context",
        "generate_answer",
    ]


def test_conditional_routing_for_invalid_question_and_missing_context(monkeypatch):
    def unexpected_retrieval(_question):
        raise AssertionError("blank question must not retrieve")

    monkeypatch.setattr(rag, "retrieve", unexpected_retrieval)
    invalid = support_agent.run_support_agent("   ")
    assert invalid["error"] == "Please provide a non-empty question."
    assert [item["node"] for item in invalid["trace"]] == [
        "validate_question",
        "handle_error",
    ]

    monkeypatch.setattr(rag, "retrieve", lambda _question: [])
    monkeypatch.setattr(
        rag,
        "generate_answer",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not generate without evidence")),
    )
    no_context = support_agent.run_support_agent("What are TrackFlow's undocumented fees?")
    assert no_context["answer"] == rag.SAFE_REFUSAL
    assert [item["node"] for item in no_context["trace"]] == [
        "validate_question",
        "retrieve_context",
        "safe_fallback",
    ]


def test_trace_order_and_checkpoint_state_are_queryable(monkeypatch):
    evidence = [{"source_document": "trackflow-sla-delivery.en.md", "text": "No standard SLA is documented."}]
    monkeypatch.setattr(rag, "retrieve", lambda _question: evidence)
    monkeypatch.setattr(rag, "generate_answer", lambda _question, context: "No standard delivery SLA is documented." if context else "")
    thread_id = f"support-test-{uuid4()}"

    result = support_agent.run_support_agent("What is the standard delivery SLA?", thread_id=thread_id)
    checkpoint = support_agent.get_support_agent_checkpoint(thread_id)

    assert result["thread_id"] == thread_id
    assert checkpoint is not None
    assert checkpoint["answer"] == result["answer"]
    assert checkpoint["trace"] == result["trace"]
    assert [entry["order"] for entry in result["trace"]] == [1, 2, 3]
    assert all(entry["output"] for entry in result["trace"])


def test_api_returns_sanitized_error_on_graph_exception(monkeypatch):
    def fail(_question):
        raise RuntimeError("provider secret details")

    monkeypatch.setattr(agent, "run_support_agent", fail)

    try:
        agent.agent_query(agent.AgentQueryRequest(question="question"))
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 500
        assert exc.detail == "The support agent could not complete this request."
        assert "provider secret details" not in str(exc.detail)
    else:
        raise AssertionError("Expected a sanitized HTTP exception")


def test_incident_status_question_routes_to_ticket_tool_not_rag(monkeypatch):
    def unexpected_retrieval(_question):
        raise AssertionError("incident questions must not call RAG retrieval")

    monkeypatch.setattr(rag, "retrieve", unexpected_retrieval)

    incident_id = str(uuid4())
    fake_result = incident_tool.IncidentLookupResult(
        found=True,
        incident_id=incident_id,
        status="in_progress",
        category="damage",
        origin="customer",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-02T00:00:00+00:00",
    )
    monkeypatch.setattr(incident_tool, "lookup_incident", lambda _request: fake_result)

    result = support_agent.run_support_agent(f"What is the status of incident {incident_id}?")

    assert result["error"] is None
    assert incident_id in result["answer"]
    assert "in_progress" in result["answer"]
    assert [entry["node"] for entry in result["trace"]] == [
        "validate_question",
        "lookup_ticket",
        "synthesize_ticket_answer",
    ]
    assert result["trace"][1]["output"]["outcome"] == "success"


def test_policy_question_routes_to_rag_not_ticket_tool(monkeypatch):
    def unexpected_lookup(_request):
        raise AssertionError("policy questions must not call the incident tool")

    monkeypatch.setattr(incident_tool, "lookup_incident", unexpected_lookup)

    evidence = [{"source_document": "trackflow-sla-delivery.en.md", "text": "No standard SLA is documented."}]
    monkeypatch.setattr(rag, "retrieve", lambda _question: evidence)
    monkeypatch.setattr(rag, "generate_answer", lambda _question, context: "No standard delivery SLA is documented." if context else "")

    result = support_agent.run_support_agent("What is TrackFlow's policy for delivery guarantees?")

    assert result["answer"] == "No standard delivery SLA is documented."
    assert [entry["node"] for entry in result["trace"]] == [
        "validate_question",
        "retrieve_context",
        "generate_answer",
    ]


def test_incident_question_without_resolvable_id_returns_honest_fallback(monkeypatch):
    def unexpected_retrieval(_question):
        raise AssertionError("fallback incident path must not call RAG retrieval")

    monkeypatch.setattr(rag, "retrieve", unexpected_retrieval)

    result = support_agent.run_support_agent("What is the status of my incident?")

    assert result["answer"] != rag.SAFE_REFUSAL
    assert "incident manager" in result["answer"].lower() or "incident id" in result["answer"].lower()
    assert [entry["node"] for entry in result["trace"]] == [
        "validate_question",
        "lookup_ticket",
        "incident_fallback",
    ]
    assert result["trace"][1]["output"]["outcome"] == "not_found"
    assert result["trace"][2]["output"]["outcome"] == "not_found"


def test_incident_lookup_timeout_is_surfaced_as_honest_fallback(monkeypatch):
    incident_id = str(uuid4())

    def timed_out(_request):
        return incident_tool.IncidentLookupResult(found=False, incident_id=incident_id, error="timeout")

    monkeypatch.setattr(incident_tool, "lookup_incident", timed_out)

    result = support_agent.run_support_agent(f"What is the status of ticket {incident_id}?")

    assert "try again" in result["answer"].lower()
    assert [entry["node"] for entry in result["trace"]] == [
        "validate_question",
        "lookup_ticket",
        "incident_fallback",
    ]
    assert result["trace"][2]["output"]["outcome"] == "timeout"
