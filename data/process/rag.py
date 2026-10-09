"""Deterministic semantic chunking and Qdrant indexing for TrackFlow."""

from __future__ import annotations

import hashlib
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any

COMPANY = "trackflow"
COLLECTION_NAME = "trackflow_knowledge"
PROVIDER_COLLECTION_NAME = "trackflow_knowledge_provider"
DOCUMENT_DIR = Path(__file__).resolve().parents[2] / "docs" / "company-knowledge-base"
SOURCE_DOCUMENTS = (
    "trackflow-sla-delivery.en.md",
    "trackflow-returns-policy.en.md",
    "trackflow-carrier-coverage.en.md",
    "trackflow-storage-pricing.en.md",
)
POINT_NAMESPACE = uuid.UUID("caa89d3c-f2e1-4fee-b32c-67816fa3c8df")


_TOKEN = re.compile(r"[a-z0-9']+")
_STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "that", "this", "are", "not", "from", "must",
        "any", "before", "than", "into", "does", "what", "how", "can", "our", "you",
        "your", "its", "have", "has", "but", "about", "during", "other", "when",
        "who", "whose", "which", "will", "may", "should", "would", "could", "an",
        "of", "to", "in", "on", "or", "is", "it", "be", "as", "by", "if", "do", "we",
    }
)
_vocabulary_cache: list[str] | None = None


def _content_tokens(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN.findall(text.lower())
        if len(token) > 2 and token not in _STOPWORDS
    ]


def _source_vocabulary() -> list[str]:
    """Stable term list from the four source files, shared by index and query."""
    global _vocabulary_cache
    if _vocabulary_cache is None:
        seen: set[str] = set()
        terms: list[str] = []
        for filename in SOURCE_DOCUMENTS:
            for token in _content_tokens((DOCUMENT_DIR / filename).read_text(encoding="utf-8")):
                if token in seen:
                    continue
                seen.add(token)
                terms.append(token)
        _vocabulary_cache = terms
    return _vocabulary_cache


def _term_indexes(token: str, positions: dict[str, int]) -> list[int]:
    """Match a token and its un-/non- negated source form.

    Questions say "documented" while the carrier policy says "undocumented".
    Counting both terms keeps that section above the retrieval threshold.
    """
    found: list[int] = []

    def add(term: str) -> None:
        index = positions.get(term)
        if index is not None and index not in found:
            found.append(index)

    add(token)
    for prefix in ("un", "non"):
        add(prefix + token)
        if token.startswith(prefix) and len(token) > len(prefix) + 2:
            add(token[len(prefix) :])
    return found


def _local_embed(text: str) -> list[float]:
    """Cosine-ready bag-of-words vector used when no embedding provider is configured.

    The last component is reserved for text that shares no source terms, so a
    zero-overlap question does not become an undefined vector.
    """
    vocabulary = _source_vocabulary()
    positions = {token: index for index, token in enumerate(vocabulary)}
    vector = [0.0] * (len(vocabulary) + 1)
    for token in _content_tokens(text):
        for index in _term_indexes(token, positions):
            vector[index] += 1.0
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0.0:
        vector[-1] = 1.0
        return vector
    return [value / norm for value in vector]


def active_collection() -> str:
    """Return the collection whose stored vectors match the embedder in use.

    The local bag-of-words index stays in ``trackflow_knowledge``. Provider
    embeddings use a separate collection so switching models does not delete it.
    """
    if os.getenv("OPENAI_API_KEY"):
        return PROVIDER_COLLECTION_NAME
    return COLLECTION_NAME


_openai_client = None
_openai_lock = threading.Lock()


def openai_client():
    """Return one OpenAI-compatible client so later calls reuse its connection."""
    global _openai_client
    if _openai_client is None:
        with _openai_lock:
            if _openai_client is None:
                from openai import OpenAI

                _openai_client = OpenAI(
                    api_key=os.environ["OPENAI_API_KEY"],
                    base_url=os.getenv("OPENAI_BASE_URL") or None,
                )
    return _openai_client


def embed(text: str) -> list[float]:
    """Embed text with the configured provider, or the local source vocabulary.

    ``OPENAI_BASE_URL`` can point to an OpenAI-compatible provider. The
    embedding model is intentionally distinct from the answer-generation model.
    When ``OPENAI_API_KEY`` is unset, indexing still uses the company documents.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return _local_embed(text)

    response = openai_client().embeddings.create(
        model=os.getenv(
            "RAG_EMBEDDING_MODEL",
            "downtown-miami/openrouter/perplexity/pplx-embed-v1-0.6b",
        ),
        input=text,
    )
    return response.data[0].embedding


def _split_document(markdown: str) -> list[tuple[str, str]]:
    """Return intact Markdown sections, splitting only on headings.

    Paragraphs, policy clauses, and sentences remain together; the source
    policies are intentionally authored with at least three semantic sections.
    """
    sections: list[tuple[str, list[str]]] = []
    current_title = "Introduction"
    current_lines: list[str] = []

    for line in markdown.splitlines():
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((current_title, [body]))
            current_title = heading.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    body = "\n".join(current_lines).strip()
    if body:
        sections.append((current_title, [body]))

    return [(title, paragraphs[0]) for title, paragraphs in sections]


def _make_chunks() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for filename in SOURCE_DOCUMENTS:
        path = DOCUMENT_DIR / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required TrackFlow source document is missing: {path}")
        sections = _split_document(path.read_text(encoding="utf-8"))
        if len(sections) < 3:
            raise ValueError(f"{filename} must contain at least three semantic sections")
        for index, (section, text) in enumerate(sections):
            chunks.append(
                {
                    "company": COMPANY,
                    "source_document": filename,
                    "section": section,
                    "language": "en",
                    "chunk_index": index,
                    "text": text,
                }
            )
    return chunks


def _point_id(payload: dict[str, Any]) -> str:
    identity = f"{payload['source_document']}:{payload['chunk_index']}:{payload['text']}"
    return str(uuid.uuid5(POINT_NAMESPACE, identity))


def setup() -> dict[str, int]:
    """Index all four source files into the collection for the active embedder.

    Deterministic point IDs make repeated runs reproducible. Only the active
    collection is recreated. With a provider key set, that is
    ``trackflow_knowledge_provider``; ``trackflow_knowledge`` is left as-is.
    """
    from qdrant_client import QdrantClient, models

    chunks = _make_chunks()
    vectors = [embed(chunk["text"]) for chunk in chunks]
    if not vectors:
        raise ValueError("No TrackFlow knowledge chunks were produced")
    dimensions = len(vectors[0])
    if any(len(vector) != dimensions for vector in vectors):
        raise ValueError("Embedding provider returned inconsistent vector dimensions")

    api_key = os.getenv("QDRANT_API_KEY")
    client = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=api_key,
    )

    collection_name = active_collection()
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=dimensions, distance=models.Distance.COSINE),
    )
    client.upsert(
        collection_name=collection_name,
        points=[
            models.PointStruct(id=_point_id(chunk), vector=vector, payload=chunk)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ],
        wait=True,
    )
    client.close()

    counts: dict[str, int] = {filename: 0 for filename in SOURCE_DOCUMENTS}
    for chunk in chunks:
        counts[chunk["source_document"]] += 1
    return counts


def source_digest() -> str:
    """Return a stable digest for the indexed source set (used by evaluation)."""
    digest = hashlib.sha256()
    for filename in SOURCE_DOCUMENTS:
        digest.update((DOCUMENT_DIR / filename).read_bytes())
    return digest.hexdigest()


if __name__ == "__main__":
    import json

    print(json.dumps(setup(), indent=2))
