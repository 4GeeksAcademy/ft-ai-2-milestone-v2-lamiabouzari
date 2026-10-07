# NIST AI controls

`POST /agent/query` rate-limits each authenticated user before `run_support_agent`. Limits are `AGENT_RATE_LIMIT_REQUESTS` and `AGENT_RATE_LIMIT_WINDOW_SECONDS`. The counter is process-local.

Model questions on `/agent/query`, `/knowledge/query`, and WebSocket `user_message` go through `normalize_model_question` (non-empty, max 2000, no control characters). That check does not delete words such as "ignore".

Each support-agent turn logs `agent_decision` with action, node, outcome, and guardrail. The log line does not include the question text.

Order ownership, carrier-override rejection, and the OWASP JWT checks stay in place. Return approval, high-value dispatch, in-transit carrier change, and cross-brand sharing are not implemented.
