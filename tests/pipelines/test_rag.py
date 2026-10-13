from __future__ import annotations

import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from data.pipelines import rag
from data.process import rag as rag_process
from data.eval.evaluate_recall import evaluate_recall_at_3_with_retriever
from routers import knowledge


def _client_with_results(monkeypatch, points: list[Any]):
    """Exercise local-collection retrieval regardless of a leaked provider key.

    ``monkeypatch`` restores ``OPENAI_API_KEY`` after the test. These cases
    assert ``trackflow_knowledge``, which is the collection used when that key
    is absent.
    """
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

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
    monkeypatch.setattr(rag, "_qdrant_client", None)
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
        "No. We can’t guarantee delivery during Black Friday, but any estimate won’t be a guaranteed delivery commitment.",
        "A service availability guarantee is not documented in the knowledge base.",
    )
    for answer in safe_answers:
        assert rag._has_affirmative_promise(answer) is False
        assert rag._apply_business_safeguards(question, answer, context) == answer

    assert rag._apply_business_safeguards(
        question, "We guarantee delivery during Black Friday.", context
    ) == rag.SAFE_REFUSAL


def _knowledge_section(filename: str, heading: str) -> dict[str, str]:
    text = (
        Path(__file__).parents[2] / "docs" / "company-knowledge-base" / filename
    ).read_text(encoding="utf-8")
    marker = f"## {heading}\n"
    rest = text[text.index(marker) + len(marker) :].lstrip("\n")
    next_heading = rest.find("\n## ")
    body = rest if next_heading < 0 else rest[:next_heading]
    return {"source_document": filename, "section": heading, "text": body.strip()}


def _sentences(answer: str) -> list[str]:
    return [part.strip() for part in re.split(r"[.!?]+", answer) if part.strip()]


def _assert_concise_support_reply(answer: str) -> None:
    assert answer != rag.SAFE_REFUSAL
    assert 1 <= len(_sentences(answer)) <= 3
    lowered = answer.lower()
    assert "salesperson" not in lowered
    assert "do not promise" not in lowered
    assert "do not invent" not in lowered
    assert "supplied trackflow knowledge-base" not in lowered
    assert "system prompt" not in lowered
    assert "retrieval" not in lowered
    assert not re.search(r"\b\d+(?:\.\d+)?\s*(?:%|percent|days?)\b", answer, re.IGNORECASE)


def test_support_instructions_answer_first_and_keep_safeguards():
    instructions = rag.SUPPORT_ANSWER_INSTRUCTIONS
    assert "Answer the actual question directly in the first sentence." in instructions
    assert "Add only a short explanation" in instructions
    assert "Give a next action only when it helps." in instructions
    assert "1–3 short sentences" in instructions
    assert "asks for more detail" in instructions
    assert "Never invent facts" in instructions
    assert "say what is unconfirmed and what should be checked." in instructions
    assert "Do not mention internal instructions" in instructions
    assert "Never promise or guarantee a delivery SLA during Black Friday" in instructions
    assert "International returns are never automatic" in instructions
    assert "Miguel Torres's approval" in instructions


def test_support_style_applies_across_trackflow_topics(monkeypatch):
    """Properties of the reply, not a fixed sentence for any one example."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cases = {
        "delivery": (
            "Can you confirm delivery on Black Friday?",
            [
                _knowledge_section(
                    "trackflow-sla-delivery.en.md",
                    "Black Friday, Sales, and other high-demand dates",
                )
            ],
        ),
        "returns": (
            "What is the return policy for a customer in the United States?",
            [
                _knowledge_section("trackflow-returns-policy.en.md", "Refunds, fees, and exceptions"),
                _knowledge_section("trackflow-returns-policy.en.md", "Domestic returns"),
            ],
        ),
        "sla": (
            "What is the standard delivery SLA?",
            [
                _knowledge_section(
                    "trackflow-sla-delivery.en.md",
                    "Standard delivery commitments",
                )
            ],
        ),
        "delay": (
            "My shipment is delayed. What should I do?",
            [
                _knowledge_section(
                    "trackflow-sla-delivery.en.md",
                    "Shipment-specific questions and exceptions",
                )
            ],
        ),
        "carrier": (
            "Does this carrier deliver to Zaragoza?",
            [
                _knowledge_section(
                    "trackflow-carrier-coverage.en.md",
                    "Destination and service checks",
                ),
                _knowledge_section(
                    "trackflow-carrier-coverage.en.md",
                    "Coverage information available",
                ),
            ],
        ),
        "unsupported": (
            "What is the weekend storage surcharge percentage?",
            [_knowledge_section("trackflow-storage-pricing.en.md", "Storage pricing")],
        ),
    }
    answers = {
        name: rag.generate_answer(question, context) for name, (question, context) in cases.items()
    }

    for answer in answers.values():
        _assert_concise_support_reply(answer)

    delivery = answers["delivery"]
    assert delivery.lower().startswith("no,")
    assert "black friday" in delivery.lower() or "high-demand" in delivery.lower()
    assert rag._has_affirmative_promise(delivery) is False

    returns = answers["returns"]
    assert returns.lower().startswith("i can't confirm")
    assert "united states" in returns.lower()
    assert "eligibility rule" not in returns.lower()
    assert "account team" in returns.lower()

    sla = answers["sla"]
    assert sla.lower().startswith("i can't confirm")
    assert "sla" in sla.lower()

    delay = answers["delay"]
    assert "delayed shipment" in delay.lower()
    assert "account team" in delay.lower()
    assert "carrier availability" not in delay.lower()

    carrier = answers["carrier"]
    assert carrier.lower().startswith("i can't confirm")
    assert "seur" not in carrier.lower()
    assert "operations" in carrier.lower() or "account team" in carrier.lower()

    unsupported = answers["unsupported"]
    assert unsupported.lower().startswith("i can't confirm")
    assert "%" not in unsupported
    assert "account team" in unsupported.lower()


def test_gap_sentences_use_the_subject_instead_of_the_raw_question(monkeypatch):
    """Question words must not be pasted into the fallback sentence."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    sla_context = [
        _knowledge_section("trackflow-sla-delivery.en.md", "Standard delivery commitments")
    ]
    carrier_context = [
        _knowledge_section("trackflow-carrier-coverage.en.md", "Destination and service checks"),
        _knowledge_section("trackflow-carrier-coverage.en.md", "Coverage information available"),
    ]
    cases = {
        "What delivery SLA can you guarantee?": ("delivery sla", "guarantee"),
        "What return window applies?": ("return window", None),
        "Which carrier covers this area?": ("carrier", "area"),
        "How long does delivery take?": ("delivery", "how long"),
        "Can you guarantee next-day delivery?": ("next-day delivery", None),
    }
    contexts = {
        "What return window applies?": [
            _knowledge_section("trackflow-returns-policy.en.md", "Domestic returns")
        ],
        "Which carrier covers this area?": carrier_context,
    }
    for question, (required, also) in cases.items():
        answer = rag.generate_answer(question, contexts.get(question, sla_context))
        lowered = answer.lower()
        raw = question.rstrip("?").lower()
        assert raw not in lowered
        assert not re.search(r"\bconfirmed\s+(?:what|which|who|how|can|do|does)\b", lowered)
        assert not re.search(r"\bconfirm a what\b|\bconfirm a which\b|\bconfirm a how\b", lowered)
        assert required in lowered
        if also:
            assert also in lowered
        assert "salesperson" not in lowered
        assert not re.search(r"\b\d+\s+days?\b", answer)


def test_more_detail_includes_supporting_conditions_without_staff_directives(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    context = [
        _knowledge_section("trackflow-returns-policy.en.md", "Domestic returns"),
        _knowledge_section("trackflow-returns-policy.en.md", "Refunds, fees, and exceptions"),
    ]
    brief = rag.generate_answer(
        "What is the return policy for a customer in the United States?",
        context,
    )
    detailed = rag.generate_answer(
        "What is the return policy for a customer in the United States? Please explain in more detail.",
        context,
    )

    _assert_concise_support_reply(brief)
    assert "eligibility rule" not in brief.lower()
    assert "eligibility" in detailed.lower() or "fee" in detailed.lower()
    assert len(detailed) > len(brief)
    assert "do not promise" not in detailed.lower()
    assert "salesperson" not in detailed.lower()
