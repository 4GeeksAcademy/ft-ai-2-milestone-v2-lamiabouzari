# TrackFlow AI inventory

Company: TrackFlow (Los Angeles, California, US, and Zaragoza, Spain).

Sensitive data in scope: B2C names, contact details, and addresses; B2B contract and volume data; integration credentials for 8 carriers.

Owners below are roles. No personal name is invented. Miguel Torres appears in the RAG prompt only as the existing approver for a storage discount, not as the owner of these systems.

Control owners:

- AI Engineering: agent, RAG, and intake model behavior
- Security/Platform Engineering: authentication, rate limits, secrets, logs
- Operations: warehouse, incident, and shipment operations
- Commercial Operations: RFP approval and client-facing commercial answers

## Implemented components

| Component | Purpose | Path | Owner | Data handled | External inputs | Model / tool | Main risk | Can act | Human approval | Third-party control |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 24/7 CX support agent | Answer tracking, returns, SLA, and incident questions | `data/pipelines/support_agent.py`, `POST /agent/query`, `WS /ws/chat/{session_id}` | AI Engineering | Support questions. Order ids are checked against the session allow-list. No address store is queried. | User question, RAG excerpts, MCP incident payloads, agent memory | OpenAI-compatible chat model via `data/pipelines/rag.py`. MCP incident/inventory tools. | Untrusted text tries to read another customer's order. | Answers only. Does not approve returns, dispatch, or change carriers. | Order data requires session ownership. Memory writes use a separate confirm/reject flow. That flow is not approval for returns, dispatch, carrier change, or cross-brand sharing. | TrackFlow owns prompts, ACL, and keys. The model host owns its infrastructure. |
| RAG over return policies and country SLAs | Retrieve TrackFlow policy excerpts and draft an answer | `data/pipelines/rag.py`, `data/process/rag.py`, `POST /knowledge/query` | AI Engineering | Policy text from `docs/company-knowledge-base/` | User question and retrieved chunks | Embedding model plus generation model. Qdrant collection `trackflow_knowledge`. | Indirect injection from retrieved text. Layered mitigation only, not complete prevention. | No. Returns text. | No separate approval before an answer. International returns stay manual in the prompt. | TrackFlow owns the corpus and Qdrant config. The embedding/chat provider owns the API. |
| WebSocket CX chat | Stream the same support agent to the backoffice | `services/chat/stream.py`, `services/routers/chat.py` | AI Engineering | Session id, user id, message text | WebSocket `user_message` text | Same support agent and generation model | Same order-injection risk, plus the JWT in the query string. Invalid text does not start a generation and does not close the socket. | Same as the CX agent | Same JWT session ownership as chat (`4401`/`4403`/`4404`) | TrackFlow owns the socket. The model host owns generation. |
| RFP intake model boundary | Classify and draft RFP intake when explicitly enabled | `data/pipelines/rfp_intake/llm.py` | Commercial Operations | RFP payload fields sent as JSON | Uploaded/structured RFP content in the payload | Optional. Default backend is local. `RFP_INTAKE_LLM=1` calls the same OpenAI-compatible gateway. | Untrusted RFP text reaches the model only when the flag is on. | Produces structured intake JSON. Does not approve the RFP. | Intake itself is not human-approved. Later RFP approval is a separate workflow. | TrackFlow owns the schema and the flag. The provider owns the API when the flag is on. |
| RFP human approval | Department reviewers approve or reject sections | `data/pipelines/rfp_approval/` | Commercial Operations | RFP section status | Reviewer decision | Not a language model | A reviewer can approve a section that should stay open. The final document still waits for every active department. | Writes approval state and the final document only after every active department is approved | Yes, for RFP sections only. This is not confirmation for return approval, dispatch, carrier change, or cross-brand sharing. | TrackFlow owns the workflow. No external model. |
| MCP incident and inventory tools | Read incidents and inventory through the API | `mcps/`, `data/pipelines/mcp_tools.py` | Security/Platform Engineering | Incident status, category, branch. Inventory product and order fields include `client_name`. | Tool arguments and backend JSON | HTTP tools, not a model. Service JWT `TRACKFLOW_API_TOKEN` when set. | Tool JSON that looks like instructions, and authenticated reads that are not brand-scoped. | Read and, where scoped, incident create/update. No return approval. | API routes require a TrackFlow JWT. MCP has its own OAuth scopes. Neither is a brand check. | TrackFlow owns the tools and the API. |
| Operational memory | Store confirmed carrier notes, recurring incidents, and report preferences | `data/pipelines/agent_memory.py` | Operations | Short operational facts. Addresses and carrier-override instructions are rejected. | User text after an explicit confirm | No model. SQLite file. | Confirmed text later treated as an operational fact. | Writes a row only after confirm and `forbidden_reason` allows it. | Yes for memory writes only. Not a control for the four CONTEXT actions. | TrackFlow owns the file. |
| Knowledge embeddings indexer | Embed trusted policy files into Qdrant | `data/process/rag.py` | AI Engineering | The four company knowledge files | File contents, not live user chat | Embedding API | A compromised knowledge file becomes retrieval context. | Writes vectors | Operators run the indexer. No per-query human approval. | TrackFlow owns the files. The provider owns the embedding API. |

## Defined in TrackFlow CONTEXT but not implemented in the current fork

- Carrier selection system. Defined in TrackFlow CONTEXT but not implemented in the current fork. There is no function that assigns a carrier. `agent_memory.forbidden_reason` still rejects "always assign the most expensive carrier" so that sentence is not stored. That rejection is not a secured carrier engine.
- Automatic returns approval, including high-value return approval. Defined in TrackFlow CONTEXT but not implemented in the current fork. No monetary threshold and no approval tool exist.
- High-value dispatch confirmation. Defined in TrackFlow CONTEXT but not implemented in the current fork.
- In-transit carrier change. Defined in TrackFlow CONTEXT but not implemented in the current fork.
- Cross-brand sharing control. Defined in TrackFlow CONTEXT but not implemented in the current fork, because `User` has no brand or `client_id`.

## External input / trust boundaries

| Source | Trust | Validation | Where it enters | Prompt-injection risk | Mitigation |
| --- | --- | --- | --- | --- | --- |
| `POST /agent/query` question | Untrusted | JWT, non-empty, max 2000, no control characters, per-user rate limit | User message. System prompt stays a separate role. | High if it could bypass order ACL | `authorize_order_access` runs before jailbreak text. Rate limit runs before `run_support_agent`. |
| WebSocket `user_message` | Untrusted | JWT on the socket, same text checks, session ownership | Same support graph | High | Same order ACL. Empty, oversized, or control-character text returns before any generation task. The socket stays open. Words such as "ignore" are not stripped. |
| `POST /knowledge/query` | Untrusted | JWT and the same text checks | RAG user content | Medium | Excerpts are marked untrusted. No order tool on this route. |
| RAG excerpts | Untrusted | `isolate_documents` drops instruction keys and neutralizes role markers | User message inside `<untrusted_excerpts>`, not the system role | High (indirect) | System prompt says excerpts are not instructions. Output guardrail blocks sensitive phrases and unowned order ids. |
| MCP / incident tool JSON | Untrusted | `isolate_tool_result` keeps known fields only | Tool data for the incident answer | Medium | Instruction keys such as `system` are discarded. |
| Agent memory rows | Untrusted until confirmed | `forbidden_reason`, then confirm/reject | Later answers as stored facts | Medium | Carrier-override phrasing and addresses are rejected before save. |
| RFP intake payload | Untrusted | Pydantic schema on the model path | Separate system prompt plus a JSON user input | Medium when `RFP_INTAKE_LLM=1` | Default path does not call a model. Approval is a human checkpoint afterward. |
| Company knowledge files | Trusted corpus, still treated as data at answer time | Indexer reads fixed filenames | Qdrant, then excerpts | Low if the files stay in git | Rebuild the collection from those files if the index is suspect. |
| Embedding and chat APIs | External | Environment base URL and key | Outbound only | Provider compromise | Keys stay in the environment. TrackFlow does not own the provider network. |

`User` has no `client_id`. Authenticated callers can still read every incident and every client KPI row. That is not brand isolation.
