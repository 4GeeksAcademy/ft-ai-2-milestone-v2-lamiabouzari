"""Deterministic semantic chunking and Qdrant indexing for TrackFlow."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path
from typing import Any

COMPANY = "trackflow"
COLLECTION_NAME = "trackflow_knowledge"
DOCUMENT_DIR = Path(__file__).resolve().parents[2] / "docs" / "company-knowledge-base"
SOURCE_DOCUMENTS = (
    "trackflow-sla-delivery.en.md",
    "trackflow-returns-policy.en.md",
    "trackflow-carrier-coverage.en.md",
    "trackflow-storage-pricing.en.md",
)
POINT_NAMESPACE = uuid.UUID("caa89d3c-f2e1-4fee-b32c-67816fa3c8df")


def embed(text: str) -> list[float]:
    """Embed text using the dedicated OpenAI-compatible embedding model.

    ``OPENAI_BASE_URL`` can point to an OpenAI-compatible provider. The
    embedding model is intentionally distinct from the answer-generation model.
    """
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )
    response = client.embeddings.create(
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
    """Rebuild ``trackflow_knowledge`` from all four complete source files.

    Deterministic point IDs make repeated runs reproducible. Recreating the
    collection also removes stale chunks when a source document changes.
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

    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=dimensions, distance=models.Distance.COSINE),
    )
    client.upsert(
        collection_name=COLLECTION_NAME,
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
