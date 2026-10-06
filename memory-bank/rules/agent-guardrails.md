# Agent Guardrails

The TrackFlow support agent in `data/pipelines/support_agent.py` keeps system instructions separate from user text, RAG documents, and MCP/tool results.

- Input jailbreaks and out-of-scope requests stop before RAG or MCP.
- Retrieved and tool content is untrusted data. Role markers such as `[SYSTEM]` are neutralized, not applied as policy.
- Order status is allowed only when `mcp_tools.authorize_order_access` confirms the authenticated session owns that order. Denial is an authorization refusal and returns no order payload.
- A shipment uses the policy of its own country. Los Angeles is the United States. Zaragoza is Spain. Cross-country policy switches are rejected.
- Answers that disclose negotiated carrier rates, commercial terms, warehouse locations, internal routes, system instructions, or another customer's order are replaced before they reach the user.
- Blocks, redirects, and quarantines record `guardrail`, `action`, and `failure_type` (`security`, `content`, or `structural`) via `data/pipelines/guardrails.py`. Those records do not include question text, order identifiers, or document contents.
