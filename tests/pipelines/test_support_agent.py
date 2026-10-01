from __future__ import annotations

from uuid import uuid4

from data.pipelines import rag, support_agent
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
