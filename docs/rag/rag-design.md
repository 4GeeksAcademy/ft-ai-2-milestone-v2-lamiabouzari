# TrackFlow RAG and knowledge-base design

## End-to-end flow

1. The source of truth is the four English Markdown policies in `docs/company-knowledge-base/`.
2. Run `python -m data.process.rag` to read all sources, split them at Markdown headings, embed every chunk, recreate the `trackflow_knowledge` Qdrant collection, and upsert the chunks with deterministic UUIDv5 point IDs.
3. `POST /knowledge/query` validates a question and calls only `data.pipelines.rag.query()`.
4. `query()` calls `retrieve()` and passes the resulting payload dictionaries to `generate_answer()`. The API returns only `{"answer": "..."}`; points, vectors, scores, and chunk details remain server-side.
5. The backoffice Knowledge Base page posts to that endpoint and renders the answer, loading state, or a clear error.

The index command intentionally recreates the collection: reruns are deterministic and stale chunks from edited/deleted source sections cannot remain. Indexing requires the configured model provider and Qdrant to be reachable.

## Semantic chunking and source coverage

Chunk boundaries are Markdown section headings. The text within each section—including its paragraphs, rules, conditions, and complete sentences—is kept intact. No arbitrary character/token truncation is performed. All four complete source documents are indexed. Every point carries `company`, `source_document`, `section`, `language`, `chunk_index`, and `text`.

| Source document | Semantic sections/chunks | Approximate size per chunk |
| --- | ---: | --- |
| `trackflow-sla-delivery.en.md` | 3 | 35–70 words |
| `trackflow-returns-policy.en.md` | 3 | 35–60 words |
| `trackflow-carrier-coverage.en.md` | 3 | 35–55 words |
| `trackflow-storage-pricing.en.md` | 3 | 30–55 words |

These four source files were added because no supplied copies were present in the repository. Their text makes explicit which details are and are not documented, and includes the required business safeguards. Before client use, TrackFlow should review/approve the policy content as authoritative source material.

## Models and vector configuration

- Embedding model ID: `downtown-miami/openrouter/perplexity/pplx-embed-v1-0.6b`, configurable with `RAG_EMBEDDING_MODEL`.
- Generation model ID: `downtown-miami/openrouter/openai/gpt-6-luna`, configurable with `RAG_GENERATION_MODEL`.
- Provider: OpenAI-compatible API, configured by `OPENAI_API_KEY` and optionally `OPENAI_BASE_URL`. No 4Geeks-specific model configuration or supported model was found in the inspected repository, so the OpenAI-compatible defaults are used; deployments may set the provider URL/model IDs to their approved endpoint.
- The embedding model and generation model are different; runtime validation rejects identical configured model IDs.
- Vector dimension: 1024 for the configured embedding model and existing `trackflow_knowledge` collection. `setup()` derives the dimension from the provider response when creating the collection, so an alternate embedding model can use its returned size.
- Qdrant collection: `trackflow_knowledge`.
- Distance: cosine (`models.Distance.COSINE`).

## Retrieval threshold and evaluation

- Default `min_score`: `0.25` cosine similarity, overridable in the function call. Qdrant applies the score threshold and the application checks it again; fewer than `k` matches, including zero, are valid.
- Threshold rationale: `0.25` is an explicit, conservative initial relevance floor rather than a claimed empirically tuned optimum. Cosine score calibration depends on the embedding model and corpus. The threshold must be reviewed against the supplied test questions after the index is available; do not lower it merely to force a desired recall result.
- Evaluation set: `data/eval/test-queries.json` (8 questions, two per source document, including Black Friday/Sales high-demand questions).
- Metric: document-level Recall@3, calculated as the average per-question fraction of expected relevant source documents present among the top three retrieved chunks. Run with `python -m data.eval.evaluate_recall` after setup.
- Result: **not run / not available in this environment**. No API credentials or live Qdrant index/service were available during implementation, so no score is claimed. Target is at least 80%; the script reports actual measured results when services are configured.

## TrackFlow-specific safeguards

The generation prompt constrains answers to retrieved text and requires an explicit insufficient-information response for gaps. It also mandates:

- Never promise a delivery SLA during Black Friday, Sales, or other declared high-demand peaks; estimates are not guarantees.
- International returns are never automatic and require manual handling.
- A storage discount requires Miguel Torres's approval; approval must not be implied or guaranteed.
- Undocumented storage discounts, storage prices, and carrier exceptions require confirmation/approval or an insufficient-information response.
- Never invent company facts, prices, percentages, SLAs, discounts, coverage, or policies.

The empty-context path returns a fixed insufficient-information answer without calling the generation model. For a policy change, update and approve its Markdown source, rerun indexing, and verify the regression/evaluation questions before representing the updated rule to a client.
