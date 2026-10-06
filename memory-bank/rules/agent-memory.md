# Agent Memory

The TrackFlow support agent keeps operational memory in its own store. This is the same agent in `data/pipelines/support_agent.py`. There is no second evaluator agent. LangGraph, MemorySaver checkpoints, RAG, MCP, guardrails, and incident routing stay in place.

## Backend

Approved facts live in a SQLite file (`data/pipelines/agent_memory.py`, default `data/agent_memory/support_memory.sqlite`). The interface is `read`, `write`, `delete`, and `list`.

SQLite fits TrackFlow because support memory must survive a new conversation, allow one pending proposal, and delete or replace rows without standing up another service. Tests point the same class at a temporary file. MemorySaver still checkpoints the graph in process memory. It is not the memory backend.

`TRACKFLOW_AGENT_MEMORY_PATH` overrides the file location.

## RAG stays read-only

Company documents stay in the `trackflow_knowledge` collection. Memory code does not import Qdrant and does not upsert into any `*_knowledge` collection. Remembering a carrier correction does not rewrite the knowledge base. RAG is still queried for ordinary support answers.

## Worth remembering

1. Corrected carrier assignment: `SEUR no longer covers that rural area of Zaragoza; use the local carrier instead.`
2. Recurring incident context: `The recurring Los Angeles delays this week are caused by the port strike.`
3. Recurring B2B report preference: `The cosmetics client wants the returns breakdown before shipment volume in the monthly report.`

## Not worth a proposal

1. `Where is package XJ4471?`
2. `Great, that's resolved.`
3. `Translate this into English for the client.`

## Never store

Even after an explicit approve or edit:

- Exact B2C or end-customer addresses
- Exact B2B physical locations, warehouse addresses, or internal routes
- Any other sensitive physical location
- A single, non-recurring package incident
- Active commercial contract negotiations
- Instruction-shaped text such as a `[SYSTEM]` override

## Confirmation

A memorable turn returns the normal reply plus one `memory_proposal`. Nothing is written yet. Only one pending proposal exists. While it is unresolved, a later memorable turn does not replace it or audit it as discarded. The proposal stays until the next message is an explicit approve, reject, edit, or an unclear topic change. Another proposal can be created only on a turn after that resolution.

The next message is classified as `approve`, `reject`, `edit`, or `unclear`. Classification uses anchored decision phrases, not a substring check such as `"yes" in message`. Ambiguity, silence, and topic changes discard the proposal and are audited as not written. If the same message both resolves the proposal and asks a new question, the proposal is resolved first and the question then follows the normal agent path.

## Poisoning defense

Memory text is untrusted data, like RAG excerpts and MCP results. Role markers are not treated as system policy. Forbidden or instruction-shaped facts are rejected at write time. When a saved fact is reused, it is appended as operational data and still passes the output guardrail. It cannot change country policy, order authorization, or the system prompt.

## Cleanup

`consolidate` runs on read and write:

- Identical normalized facts collapse to one row.
- Carrier rules are keyed by carrier, country, and area (`rural` or `general`). Zaragoza and Spain normalize to Spain. Los Angeles and the United States normalize to the United States. A new rule for the same key replaces the old one.
- Recurring incident context expires after 7 days when it says "this week", otherwise after 14 days.
- B2B preferences stay until a newer preference for that client replaces them.

## Single agent

Proposal, confirmation, audit, and reuse are functions called by `run_support_agent` and the existing answer node. Guardrails still run before tools and before the user sees an answer.
