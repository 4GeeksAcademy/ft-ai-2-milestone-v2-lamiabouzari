# TrackFlow NIST Cybersecurity Framework — AI security

Company: TrackFlow, operating in Los Angeles, California, US, and Zaragoza, Spain.

This report covers the AI and agent paths that exist in this fork. It reuses the OWASP controls in `docs/security/owasp-top10-report.md` instead of replacing them.

Regulatory obligations named here:

- GDPR and the Spanish AEPD. When a personal-data breach is likely to risk individuals' rights and freedoms, the engineering response must support notification to the AEPD within 72 hours of becoming aware of it.
- CCPA/CPRA. California consumers have access, deletion, and opt-out rights. A security breach that affects California consumers requires a reasonably prompt notification assessment. This document assigns engineering work. It is not a legal conclusion.

## GOVERN

- Current state: Roles are assigned in `docs/security/ai-inventory.md`. AI Engineering owns the CX agent and RAG. Security/Platform Engineering owns JWT, secrets, and the new rate limit. Commercial Operations owns RFP approval. Operations owns incident and memory facts. These four CONTEXT actions are not implemented in the current fork, so no human confirmation is claimed for them: high-value return approval is not implemented in the current fork; high-value dispatch is not implemented; in-transit carrier change is not implemented; cross-brand sharing control is not implemented because the brand isolation model does not exist. RFP department approval and agent-memory confirm/reject are separate examples. They are not controls for those four actions.
- Repository evidence: inventory, `services/dependencies.py`, `data/pipelines/rfp_approval/`, `data/pipelines/agent_memory.py`.
- Gaps: No named privacy officer in the repository. No brand tenant owner, because `User` has no `client_id`.
- Action: Keep the inventory current when a carrier engine or returns tool is added, and require human confirmation before that tool can execute.
- Priority: high.
- Owner: Security/Platform Engineering, with Commercial Operations for client data.
- Verification / success criteria: inventory lists every model call site found by searching `chat.completions`. A new action tool without a confirmation gate fails review.

Third parties: TrackFlow owns API keys, prompts, and tool ACLs. The OpenAI-compatible host and Qdrant vendor own their platforms. MCP OAuth is configured from the environment.

## IDENTIFY

- Current state: The inventory lists the CX agent, RAG, WebSocket chat, optional RFP intake model, embeddings indexer, MCP tools, and operational memory. Carrier selection and automatic returns approval are marked not implemented. Sensitive data is B2C contact and address data, B2B contract and volume data, and carrier credentials. Trust boundaries are in the inventory table.
- Repository evidence: `docs/security/ai-inventory.md`. Order ACL in `data/pipelines/mcp_tools.py`. OWASP report residual: authenticated users still see every client KPI row.
- Gaps: No per-brand `client_id`. WebSocket JWT remains in the query string. `python-jose` 3.5.0 `CVE-2026-85394` and `ecdsa` 0.19.2 `PYSEC-2026-1325` are still two unique advisories with no fix version from pip-audit.
- Action: Do not claim tenant isolation. Add a real client id before any B2B portal shares volume or incidents.
- Priority: high for tenant isolation. Medium for the dependency advisories until an upstream fix exists.
- Owner: Security/Platform Engineering.
- Verification / success criteria: `User` model has no `client_id`. Security tests still show anonymous KPI access is 401 while authenticated reads are not filtered by brand.

## PROTECT

- Current state: OWASP JWT checks remain on incidents, inventory, reporting, telemetry report, task status, `/agent/query`, and `/knowledge/query`. Secrets (`JWT_SECRET`, `OPENAI_API_KEY`, `QDRANT_API_KEY`, `TRACKFLOW_API_TOKEN`, `RESEND_API_KEY`) come from the environment. `.env.example` has placeholders only. Order prompt injection is denied by `authorize_order_access` before the model. These are layered mitigations, not complete prompt-injection prevention. The system instruction stays in the system role. RAG excerpts sit in `<untrusted_excerpts>` and are not system authority. MCP instruction-like keys are dropped before they can become model authority. User or tool text cannot change the order allow-list. `POST /agent/query` is rate-limited per authenticated user id before `run_support_agent`. Questions must be non-empty, at most 2000 characters, and free of control characters. Words such as "ignore" are not stripped.
- Repository evidence: `services/agent_rate_limit.py`, `services/model_input.py`, `services/routers/agent.py`, `data/pipelines/rag.py`, `tests/security/`.
- Gaps: The rate limit is process-local. Chat tokens are still in the WebSocket query string and in `localStorage`. Production TLS was not verified on a host.
- Action: Put a shared limiter in front of every worker before production scale-out. Keep carrier keys out of git.
- Priority: high for the rate limit in production (move off process memory). Medium for the socket token transport.
- Owner: Security/Platform Engineering.
- Verification / success criteria: `tests/security/test_nist_controls.py` shows 200 under the limit, 429 over the limit, no second model call, separate counters per user, and 422 for empty, oversized, and control-character input.

Least privilege: the CX agent has no return, dispatch, or carrier-change tool. Memory writes still pass `forbidden_reason` and an explicit confirm.

## DETECT

- Current state: Both a normal completed support turn and a guardrail refusal log `agent_decision` with action, node, outcome, and guardrail. The line does not include the JWT, API key, password, full user question, delivery address, or other unnecessary PII. Guardrail events log name, action, and failure type. JWT failures log "authentication failed: invalid or expired token". Access denials log "access denied". Rate-limit rejections log `agent_rate_limited` without the token.
- Repository evidence: `data/pipelines/support_agent.py` `_log_agent_decision`, `data/pipelines/guardrails.py` `record_guardrail`, `services/dependencies.py`, `services/exceptions.py`.
- Gaps: Logs stay on the process. There is no SIEM, pager, or centralized alert. A prompt-injection refusal is visible in the log only if someone reads it.
- Action: Ship process logs to the host log stack. Alert on `guardrail=unauthorized_order` and `agent_rate_limited`.
- Priority: medium.
- Owner: Security/Platform Engineering.
- Verification / success criteria: `test_agent_decision_log_records_refusal_without_address` expects `outcome=refused` and `guardrail=unauthorized_order`, and expects the street address to be absent from that line.

## RESPOND

- Current state: No live incident-response system is running in this repository. The procedure below is the engineering runbook. It is not a legal determination.
- Repository evidence: `POST /agent/query`, `/knowledge/query`, `WS /ws/chat/{session_id}`, `RFP_INTAKE_LLM`, `TRACKFLOW_API_TOKEN`, Qdrant collection `trackflow_knowledge`, and `agent_decision` process logs.
- Gaps: No on-call rotation, ticket system, or automated AEPD or CCPA filing exists in the repo.
- Action: Contain first. Disable the affected route or remove the model key so `/agent/query`, `/knowledge/query`, and the chat socket stop calling the provider. Set `RFP_INTAKE_LLM` off. Revoke `TRACKFLOW_API_TOKEN` and MCP client tokens if tools were involved. Preserve process logs, agent decision lines, and a Qdrant snapshot. Identify affected user ids and order ids without copying extra addresses into the ticket. Rotate `JWT_SECRET`, `OPENAI_API_KEY`, `QDRANT_API_KEY`, carrier credentials, `TRACKFLOW_API_TOKEN`, and `RESEND_API_KEY` if they could have been read. GDPR / AEPD: if B2C names, contacts, or addresses may have been exposed, assess whether the breach risks individuals' rights and freedoms; when that risk is present, support notification to the AEPD within 72 hours of awareness. CCPA/CPRA: if California consumers are affected, assess consumer impact and reasonably prompt breach notification, and record later access, deletion, or opt-out requests. Engineering supplies the timeline and does not send the legal notice. Commercial Operations speaks to B2B clients. Operations speaks to warehouse leads.
- Priority: high.
- Owner: Security/Platform Engineering for containment and evidence. Commercial Operations for client communication.
- Verification / success criteria: this section names GDPR, AEPD, the 72-hour notification requirement, and CCPA/CPRA, and names the TrackFlow components to disable. No production incident was executed.

## RECOVER

- Current state: Recovery is a documented procedure, not an executed production restore. Service config lives in this repository's compose file and `services/Dockerfile`.
- Repository evidence: `docker-compose.yml`, `services/Dockerfile`, `data/process/rag.py`, `docs/company-knowledge-base/`, and `authorize_order_access`.
- Gaps: No backup restore was run on a host. There is no SIEM to watch after reopen. Redis, Qdrant, and Flower must stay on `127.0.0.1`.
- Action: Rotate the secrets listed under RESPOND and restart the API, worker, and chat process. Restore from the known compose and Docker config. Do not turn `--reload` back on or republish Redis, Qdrant, or Flower on every interface. If the RAG index is suspect, rebuild `trackflow_knowledge` from `docs/company-knowledge-base/` with `data/process/rag.py`, not from chat transcripts. Invalidate old JWTs by rotating `JWT_SECRET` and recreate MCP service tokens. Confirm the CX agent still has no return, dispatch, or carrier-change tool and that `authorize_order_access` denies unowned orders. Before reopening, run `tests/security`, `tests/pipelines/test_guardrails.py`, `tests/pipelines/test_rfp_sse.py`, and `tests/pipelines/test_websocket_chat.py`. Then read `agent_decision` refusals and `agent_rate_limited` in the process log.
- Priority: high.
- Owner: Security/Platform Engineering, with AI Engineering for the Qdrant rebuild.
- Verification / success criteria: those test suites pass before the service is reopened. Production restore was not performed in this audit.

## Open gaps

| Gap | Risk | Why it remains | Mitigation | Priority | Owner |
| --- | --- | --- | --- | --- | --- |
| No `client_id` on `User` | Authenticated staff can read every client's incidents and KPI rows | No B2B portal and no tenant key exist. Inventing one would be a new product. | Add a real client id before brand-facing access. | High | Security/Platform Engineering |
| Process-local rate limit | A second worker has its own counter | Redis is present for Celery, but the limiter was kept in-process so tests stay deterministic | Move the counter to Redis before multiple API workers | Medium | Security/Platform Engineering |
| Process-local logs | Refusals are not alerted | No SIEM is configured in the repo | Ship logs and alert on `unauthorized_order` and `agent_rate_limited` | Medium | Security/Platform Engineering |
| WebSocket JWT in the query string | Tokens can land in proxy logs | Changing the handshake would risk the Milestone 10 chat flow | Later cookie or subprotocol, with the chat suite retested | Medium | AI Engineering |
| JWT in `localStorage` | XSS can read the backoffice token | Cookie auth would be a second auth system | Keep server checks. Review XSS sinks. | Medium | Security/Platform Engineering |
| `python-jose` / `ecdsa` advisories | 3 scan rows, 2 unique advisories, no fix version | Upgrading without a fix would be a guess | Re-scan when a patched release exists | High residual | Security/Platform Engineering |
| Production TLS, sshd, firewall | Host settings were not observed | This environment has the repository only | Follow `docs/security/server-hardening.md` on the server | High for deploy | Operations |
| Four CONTEXT high-impact actions | None can be confirmed by a human because they are not built | No return threshold, dispatch confirm, in-transit carrier change, or cross-brand share tool | If one is added, block execution until an explicit confirm | High when built | Operations and Commercial Operations |
