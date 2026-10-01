"""Reproducible document-level Recall@3 evaluation for TrackFlow RAG."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# This file is also invoked directly by the evaluation pipeline. Add the
# repository root before importing the application package so that invocation
# does not depend on the current interpreter's path configuration.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.pipelines.rag import retrieve
QUERY_FILE = ROOT / "data" / "eval" / "test-queries.json"


def evaluate_recall_at_3(queries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Evaluate hit-rate Recall@3; each query names one or more relevant files.

    Per-query recall is relevant source-document coverage among the expected
    documents. Retrieval is genuinely performed by the configured live index.
    """
    if queries is None:
        queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    outcomes = []
    for item in queries:
        results = retrieve(item["question"], k=3)
        retrieved = {result.get("source_document") for result in results}
        expected = set(item["relevant_documents"])
        recall = len(expected & retrieved) / len(expected) if expected else 0.0
        outcomes.append(
            {
                "question": item["question"],
                "expected": sorted(expected),
                "retrieved": sorted(source for source in retrieved if source),
                "recall": recall,
            }
        )
    score = sum(item["recall"] for item in outcomes) / len(outcomes) if outcomes else 0.0
    return {"metric": "Recall@3", "queries": len(outcomes), "score": score, "results": outcomes}


def evaluate_recall_at_3_with_retriever(queries: list[dict[str, Any]], retriever) -> dict[str, Any]:
    """Evaluate Recall@3 with an injected retriever for repeatable fixtures."""
    outcomes = []
    for item in queries:
        results = retriever(item["question"], k=3)
        retrieved = {result.get("source_document") for result in results}
        expected = set(item["relevant_documents"])
        recall = len(expected & retrieved) / len(expected) if expected else 0.0
        outcomes.append({"question": item["question"], "recall": recall})
    score = sum(item["recall"] for item in outcomes) / len(outcomes) if outcomes else 0.0
    return {"metric": "Recall@3", "queries": len(outcomes), "score": score, "results": outcomes}


if __name__ == "__main__":
    print(json.dumps(evaluate_recall_at_3(), indent=2))
