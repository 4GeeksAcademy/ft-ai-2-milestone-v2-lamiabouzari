from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from data.pipelines import rag
from data.process import rag as rag_process
from data.eval.evaluate_recall import evaluate_recall_at_3_with_retriever
from routers import knowledge


def _client_with_results(monkeypatch, points: list[Any]):
    class FakeClient:
        closed = False

        def query_points(self, **kwargs):
            assert kwargs["collection_name"] == "trackflow_knowledge"
            assert kwargs["with_vectors"] is False
            return type("Result", (), {"points": points})()

        def close(self):
            self.closed = True

    fake = FakeClient()
    qdrant = ModuleType("qdrant_client")
    qdrant.QdrantClient = lambda **kwargs: fake
    class Filter:
        def __init__(self, **kwargs):
            pass

    class FieldCondition:
        def __init__(self, **kwargs):
            pass

    class MatchValue:
        def __init__(self, **kwargs):
            pass

    qdrant.models = type(
        "Models",
        (),
        {"Filter": Filter, "FieldCondition": FieldCondition, "MatchValue": MatchValue},
    )
    monkeypatch.setitem(sys.modules, "qdrant_client", qdrant)
    monkeypatch.setattr(rag, "embed", lambda _text: [0.1, 0.2])
    return fake


def _point(payload: dict[str, Any], score: float):
    return type("Point", (), {"payload": payload, "score": score})()


def test_retrieve_filters_below_min_score(monkeypatch):
    _client_with_results(
        monkeypatch,
        [
            _point({"text": "good", "company": "trackflow"}, 0.8),
            _point({"text": "weak", "company": "trackflow"}, 0.2),
        ],
    )

    assert rag.retrieve("delivery", k=2, min_score=0.25) == [
        {"text": "good", "company": "trackflow"}
    ]


def test_retrieve_may_return_fewer_than_k(monkeypatch):
    _client_with_results(monkeypatch, [_point({"text": "one"}, 0.9)])

    assert rag.retrieve("question", k=5) == [{"text": "one"}]


def test_retrieve_may_return_zero_results(monkeypatch):
    _client_with_results(monkeypatch, [])

    assert rag.retrieve("unknown", k=3) == []


def test_query_calls_retrieval_and_generation(monkeypatch):
    context = [{"text": "approved evidence"}]
    calls = []
    monkeypatch.setattr(rag, "retrieve", lambda question: calls.append(("retrieve", question)) or context)
    monkeypatch.setattr(
        rag,
        "generate_answer",
        lambda question, received: calls.append(("generate", question, received)) or "Generated answer",
    )

    assert rag.query("client asks") == "Generated answer"
    assert calls == [("retrieve", "client asks"), ("generate", "client asks", context)]


def test_query_returns_generated_output_not_raw_chunk(monkeypatch):
    monkeypatch.setattr(rag, "retrieve", lambda _question: [{"text": "internal chunk contents"}])
    monkeypatch.setattr(rag, "generate_answer", lambda _question, _context: "Client-ready response")

    result = rag.query("question")

    assert result == "Client-ready response"
    assert "internal chunk contents" not in result


def test_knowledge_endpoint_returns_answer_only_and_uses_retrieved_context(monkeypatch):
    retrieved = [{"text": "The approved policy answer is manual handling."}]
    observed = {}

    monkeypatch.setattr(knowledge, "query", lambda question: rag.query(question))
    monkeypatch.setattr(rag, "retrieve", lambda question: observed.setdefault("question", question) and retrieved)

    def generate_answer(question, context):
        observed["context"] = context
        return "International returns require manual handling."

    monkeypatch.setattr(rag, "generate_answer", generate_answer)
    response = knowledge.knowledge_query(knowledge.KnowledgeQueryRequest(question="How are international returns handled?"))

    assert response.model_dump() == {"answer": "International returns require manual handling."}
    assert observed["context"] == retrieved


def test_insufficient_context_does_not_call_model_or_invent(monkeypatch):
    openai = ModuleType("openai")
    openai.OpenAI = lambda **_kwargs: (_ for _ in ()).throw(
        AssertionError("generation model must not run without context")
    )
    monkeypatch.setitem(sys.modules, "openai", openai)

    answer = rag.generate_answer("What is the rate?", [])

    assert "don’t have enough confirmed information" in answer
    assert "€" not in answer


def test_setup_chunks_all_documents_at_semantic_sections():
    chunks = rag_process._make_chunks()
    counts = {filename: 0 for filename in rag_process.SOURCE_DOCUMENTS}
    for chunk in chunks:
        counts[chunk["source_document"]] += 1
        assert set(chunk) == {
            "company", "source_document", "section", "language", "chunk_index", "text"
        }
        assert chunk["company"] == "trackflow"
        assert chunk["language"] == "en"
        assert chunk["text"].strip()
    assert all(count >= 3 for count in counts.values())


def test_recall_at_3_evaluation_is_reproducible_with_fixture():
    queries = [
        {"question": "SLA?", "relevant_documents": ["sla.md"]},
        {"question": "Returns?", "relevant_documents": ["returns.md"]},
    ]
    result = evaluate_recall_at_3_with_retriever(
        queries,
        lambda question, *, k: [
            {"source_document": "sla.md" if question == "SLA?" else "returns.md"}
        ][:k],
    )

    assert result["metric"] == "Recall@3"
    assert result["queries"] == 2
    assert result["score"] == 1.0



def test_normalized_numeric_claims_include_written_percentage_units():
    assert rag._normalized_numeric_claims("15%, 15 percent, 15 percentage") == {
        ("15", "percent")
    }
    assert rag._normalized_numeric_claims(
        "30 days, 30-day; 48 hours, 48-hour; $100, USD 100; €25, 25 EUR"
    ) == {
        ("30", "day"),
        ("48", "hour"),
        ("100", "usd"),
        ("25", "eur"),
    }


def test_delivery_promise_negations_are_not_affirmative():
    question = "Is delivery guaranteed during Black Friday?"
    context = [{"text": "Delivery estimates vary during Black Friday."}]
    safe_answers = (
        "There is no guarantee during Black Friday.",
        "Delivery is not guaranteed during Black Friday.",
        "Delivery is never guaranteed during Black Friday.",
        "Delivery isn't guaranteed during Black Friday.",
        "Delivery aren't guaranteed during Black Friday.",
        "We cannot guarantee delivery during Black Friday.",
        "We can't guarantee delivery during Black Friday.",
        "We won't guarantee delivery during Black Friday.",
    )
    for answer in safe_answers:
        assert rag._has_affirmative_promise(answer) is False
        assert rag._apply_business_safeguards(question, answer, context) == answer

    assert rag._apply_business_safeguards(
        question, "We guarantee delivery during Black Friday.", context
    ) == rag.SAFE_REFUSAL
