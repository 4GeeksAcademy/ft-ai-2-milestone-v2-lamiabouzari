# TrackFlow — Telemetry Plan

> Company: **TrackFlow**
>
> Scope: this document defines the event catalogue, the standard event envelope,
> and the delivery strategy for TrackFlow telemetry based on the authoritative
> requirements provided for this assignment.

---

## 1. Standard Event Envelope

Every TrackFlow event uses the same envelope. Event-specific details live under
`properties`.

| Field | Type | Purpose |
|---|---|---|
| `eventId` | string (UUID) | Unique identifier of this event instance. |
| `timestamp` | string (ISO 8601, UTC) | Moment the event occurred, used for ordering and time-based analysis. |
| `sessionId` | string (UUID) | Unique session identifier for the user journey without exposing personal data. |
| `userId` | string (stable internal ID) | The internal acting user, never a name, email, or other PII. |
| `event_type` | string (snake_case) | Canonical event name from the catalogue. |
| `schemaVersion` | string (semver, e.g. `"1.0.0"`) | Schema version for safe evolution and compatibility. |
| `requestId` | string (UUID) or null | Correlates the event with the backend request or trace that produced it. |
| `properties` | object | Event-specific payload validated by the allowlist. |

Required envelope fields: `eventId`, `timestamp`, `sessionId`, `userId`, `event_type`, `schemaVersion`, `requestId`, `properties`.

**Identifier policy**: `userId`, `sessionId`, `client_id`, `product_id`, `requestId`, and `eventId` are stable opaque identifiers. Names, emails, addresses, and other human-identifying values are never placed in the event envelope or `properties`.

---

## 2. Authoritative Business Constraints

1. **Stock is never modified directly.** All stock changes happen through `InboundOrder` or `OutboundOrder` events; direct-write attempts are rejected and logged by `direct_stock_edit_rejected`.
2. **Stock changes happen through `InboundOrder` or `OutboundOrder`.** Inventory mutations are traceable to their originating order events.
3. **Every stock-changing operation is traceable to a user.** The acting user is present in the standard `userId` envelope field for each relevant event.
4. **Each SKU belongs to one client.** Every inventory event contains both `client_id` and `product_id`.
5. **No carrier information is collected in inventory telemetry.** No carrier name, tracking number, or shipping-partner ID is allowed.
6. **No recipient/end-consumer personal data is collected.** No recipient name, address, phone, or email appears in telemetry.
7. **Passwords, tokens, and credentials are excluded.** No password, token, session cookie, or credential material is ever logged.

---

## 3. Event Type List (16 total)

- `inbound_order_created`
- `outbound_order_created`
- `stock_threshold_triggered`
- `direct_stock_edit_rejected`
- `inventory_discrepancy_detected`
- `inventory_count_recorded`
- `user_login_succeeded`
- `user_login_failed`
- `permission_denied`
- `api_request_failed`
- `background_job_failed`
- `page_load_measured`
- `search_query_executed`
- `backoffice_page_viewed`
- `order_creation_abandoned`
- `report_export_requested`

Total: **16 events** — **5 mandatory** and **11 additional**.

All inventory events include the mandatory TrackFlow inventory properties:
`warehouse`, `client_id`, `product_id`, `product_category`, and `quantity`.

---

## 4. Event Catalogue

### 4.1 Inventory / Business Operations

#### `inbound_order_created` — mandatory
- Hypothesis: We need to understand how stock enters each warehouse, by client and category.
- Concrete decision: Forecast receiving capacity and staffing needs.
- Allowlist:
  - `warehouse` — enum(`los_angeles`,`zaragoza`) — required
  - `client_id` — string — required
  - `product_id` — string — required
  - `product_category` — enum(`fashion`,`electronics`,`cosmetics`) — required
  - `quantity` — integer, minimum 1 — required
  - `order_id` — string — required
  - `source_type` — enum(`purchase_order`,`return`,`transfer`) — optional
- Delivery: **batch**
- Business / operational justification: This event records inbound stock movement at the ledger level, which is used for aggregate receiving analysis, capacity planning, and operational forecasting.
- Sensitive / PII handling: No carrier or recipient data is collected. Only opaque internal IDs are used.

#### `outbound_order_created` — mandatory
- Hypothesis: We need to know outbound velocity by warehouse, client, and category.
- Concrete decision: Prioritize replenishment planning and picking resources.
- Allowlist:
  - `warehouse` — enum(`los_angeles`,`zaragoza`) — required
  - `client_id` — string — required
  - `product_id` — string — required
  - `product_category` — enum(`fashion`,`electronics`,`cosmetics`) — required
  - `quantity` — integer, minimum 1 — required
  - `order_id` — string — required
  - `destination_type` — enum(`customer_shipment`,`return_to_supplier`,`transfer`) — optional
- Delivery: **batch**
- Business / operational justification: Batch-level dispatch telemetry supports demand analysis and operational planning without exposing carrier or recipient details.
- Sensitive / PII handling: No carrier data or recipient/end-consumer personal data is collected. `destination_type` is an internal classification only.

#### `stock_threshold_triggered` — mandatory
- Hypothesis: We need to know when a SKU is near or below the inventory floor threshold.
- Concrete decision: Trigger replenishment before fulfillment is disrupted.
- Allowlist:
  - `warehouse` — enum(`los_angeles`,`zaragoza`) — required
  - `client_id` — string — required
  - `product_id` — string — required
  - `product_category` — enum(`fashion`,`electronics`,`cosmetics`) — required
  - `quantity` — integer, minimum 0 — required
  - `threshold_value` — integer — required
- Delivery: **stream**
- Business / operational justification: Stockout-risk signals need near-real-time visibility so replenishment teams can act before service disruption occurs.
- Sensitive / PII handling: No personal data is collected; only warehouse, client, product, and threshold metadata are logged.

#### `direct_stock_edit_rejected` — mandatory
- Hypothesis: We need to detect and quantify attempts to bypass the approved inventory workflow.
- Concrete decision: Enforce process controls and access restrictions when direct stock edits are attempted.
- Allowlist:
  - `warehouse` — enum(`los_angeles`,`zaragoza`) — required
  - `client_id` — string — required
  - `product_id` — string — required
  - `product_category` — enum(`fashion`,`electronics`,`cosmetics`) — required
  - `quantity` — integer — required
  - `attempted_by_user_id` — string — required
  - `rejection_reason` — string — optional
- Delivery: **stream**
- Business / operational justification: This is a security and integrity event that must be surfaced promptly to control misuse and protect inventory accuracy.
- Sensitive / PII handling: No personal identifiers beyond an internal stable user ID are included. No credentials or tokens are recorded.

#### `inventory_discrepancy_detected` — mandatory
- Hypothesis: We need to understand where and how often expected stock diverges from actual stock.
- Concrete decision: Prioritize audits and root-cause analysis for reconciliation issues.
- Allowlist:
  - `warehouse` — enum(`los_angeles`,`zaragoza`) — required
  - `client_id` — string — required
  - `product_id` — string — required
  - `product_category` — enum(`fashion`,`electronics`,`cosmetics`) — required
  - `quantity` — integer — required
  - `expected_quantity` — integer — required
  - `actual_quantity` — integer — required
- Delivery: **batch**
- Business / operational justification: Reconciliation mismatches are evaluated in audit cycles and operational reporting rather than as immediate per-event alerts.
- Sensitive / PII handling: No personal data, carrier metadata, or recipient details are included.

#### `inventory_count_recorded` — additional
- Hypothesis: We need to know which SKUs are actually being physically counted and how frequently audit coverage occurs.
- Concrete decision: Prioritize audit schedules and warehouse resources for SKUs or locations that are not being counted frequently enough.
- Allowlist:
  - `warehouse` — enum(`los_angeles`,`zaragoza`) — required
  - `client_id` — string — required
  - `product_id` — string — required
  - `product_category` — enum(`fashion`,`electronics`,`cosmetics`) — required
  - `quantity` — integer — required
- Delivery: **batch**
- Business / operational justification: This event records a physical inventory count taken during an audit or cycle count. It does not modify stock and supports warehouse audit coverage analysis.
- Sensitive / PII handling: No personal or carrier data is collected. Only audit context and inventory identifiers are retained.

### 4.2 Authentication / Security

#### `user_login_succeeded` — additional
- Hypothesis: We need to understand usage patterns and access volume across internal users.
- Concrete decision: Right-size licensing and detect unusual access patterns.
- Allowlist:
  - `auth_method` — enum(`password`,`sso`,`mfa`) — required
  - `warehouse` — enum(`los_angeles`,`zaragoza`) — optional
- Delivery: **batch**
- Business / operational justification: This gives a usage baseline for monitoring access patterns and changes in system adoption.
- Sensitive / PII handling: The event records only the authentication method and optional site context. No password, token, or credential material is collected.

#### `user_login_failed` — additional
- Hypothesis: We need to detect repeated failed authentication attempts and potential attack patterns.
- Concrete decision: Trigger lockout workflows and security review.
- Allowlist:
  - `auth_method` — enum(`password`,`sso`,`mfa`) — required
  - `failure_reason` — enum(`invalid_credentials`,`account_locked`,`mfa_failed`,`unknown`) — required
- Delivery: **stream**
- Business / operational justification: Failed logins are a near-real-time security signal that should be examined quickly to prevent brute force or takeover attempts.
- Sensitive / PII handling: No credentials, tokens, or raw password values are recorded.

#### `permission_denied` — additional
- Hypothesis: We need to measure authorization failures and identify misconfigured roles or probing attempts.
- Concrete decision: Adjust role policy or investigate suspicious behavior.
- Allowlist:
  - `resource_type` — string — required
  - `action` — string — required
- Delivery: **stream**
- Business / operational justification: Permission denials are a security signal and should be visible quickly for operational review.
- Sensitive / PII handling: No user names, address details, or credential material are stored.

### 4.3 Errors

#### `api_request_failed` — additional
- Hypothesis: We need to identify which API surfaces fail most often and under what conditions.
- Concrete decision: Prioritize endpoint reliability fixes and infrastructure investments.
- Allowlist:
  - `endpoint` — string — required
  - `http_status` — integer — required
  - `error_code` — string — optional
- Delivery: **stream**
- Business / operational justification: API failures require prompt detection to support incident response and reliable service operations.
- Sensitive / PII handling: No request payload or user content is logged. Only route and status metadata are retained.

#### `background_job_failed` — additional
- Hypothesis: We need to know which scheduled or asynchronous jobs fail and how frequently.
- Concrete decision: Prioritize fixes to the jobs protecting stock accuracy and operational integrity.
- Allowlist:
  - `job_name` — string — required
  - `error_code` — string — optional
- Delivery: **batch**
- Business / operational justification: Scheduled job failures are operationally important but generally reviewed in aggregate rather than processed as a per-event real-time alert.
- Sensitive / PII handling: No personal data or credentials are recorded.

### 4.4 Performance

#### `page_load_measured` — additional
- Hypothesis: We need to know which screens are slowest for internal users.
- Concrete decision: Prioritize front-end optimization on the pages with the worst performance.
- Allowlist:
  - `page_name` — string — required
  - `duration_ms` — integer, minimum 0 — required
- Delivery: **batch**
- Business / operational justification: Performance trends are gathered in aggregate and sampled to manage volume while preserving visibility into slow pages.
- Sensitive / PII handling: No user content, personal identifiers, or raw URLs with query parameters are stored.

#### `search_query_executed` — additional
- Hypothesis: We need to know how users search for inventory and operational data, without collecting the raw query text.
- Concrete decision: Improve search UX and indexing for the most common query patterns.
- Allowlist:
  - `search_context` — enum(`inventory`,`orders`,`clients`) — required
  - `result_count` — integer, minimum 0 — required
  - `duration_ms` — integer, minimum 0 — optional
- Delivery: **batch**
- Business / operational justification: Search telemetry supports product UX decisions and indexing improvements while avoiding incidental PII capture.
- Sensitive / PII handling: Raw free-text queries are not recorded. Only context and result metrics are captured.

### 4.5 Navigation / Backoffice Usage

#### `backoffice_page_viewed` — additional
- Hypothesis: We need to understand which backoffice screens are used most often and where users spend time.
- Concrete decision: Prioritize UX and process changes based on actual adoption patterns.
- Allowlist:
  - `page_name` — string — required
  - `referrer_page_name` — string — optional
- Delivery: **batch**
- Business / operational justification: High-volume page-view telemetry is best handled in aggregated batches and debounced to preserve signal while limiting noise.
- Sensitive / PII handling: No names, emails, or URL parameters with user data are recorded.

#### `order_creation_abandoned` — additional
- Hypothesis: We need to identify where users abandon order creation flows.
- Concrete decision: Reduce friction in the creation process and improve conversion at the abandonment point.
- Allowlist:
  - `order_type` — enum(`inbound`,`outbound`) — required
  - `last_step_reached` — string — required
  - `warehouse` — enum(`los_angeles`,`zaragoza`) — optional
- Delivery: **batch**
- Business / operational justification: Funnel analysis is aggregated and reviewed in batches rather than as a real-time operational alert.
- Sensitive / PII handling: No recipient or carrier details are included.

#### `report_export_requested` — additional
- Hypothesis: We need to know which reports are exported most often by internal users.
- Concrete decision: Prioritize native dashboard or export feature investment based on actual demand.
- Allowlist:
  - `report_type` — enum(`inventory_summary`,`order_history`,`discrepancy_audit`) — required
  - `export_format` — enum(`csv`,`pdf`) — required
  - `warehouse` — enum(`los_angeles`,`zaragoza`) — optional
- Delivery: **batch**
- Business / operational justification: Export usage is a reporting and product-usage signal rather than a real-time operational event.
- Sensitive / PII handling: The event records only the request metadata, not the exported file contents or customer data.

---

## 5. Sensitive Data Handling

- No passwords, tokens, API keys, or session cookies are recorded in any event.
- No carrier information is captured in any inventory-related event.
- No recipient/end-consumer names, addresses, phone numbers, or email addresses are captured.
- Only opaque stable internal identifiers are allowed in the envelope or event properties.
- Free-text and raw URL query strings are excluded from the property allowlist to avoid incidental PII exposure.

---

## 6. Risks and Exclusions

### Risks
- **Threshold noise**: Frequent threshold churn can create noisy operational alerts; mitigation is hysteresis or a minimum dwell period before re-firing.
- **Schema drift**: Changing the property allowlist without a schema-version bump can break downstream consumers; therefore `schemaVersion` must be included and incremented for breaking changes.
- **Re-identification risk**: Even stable IDs can become identifiable when joined to other systems; only authorized staff should have telemetry-join access.

### Exclusions
- Carrier identity, carrier tracking numbers, and last-mile carrier metadata are never collected.
- Recipient/end-consumer personal data is never collected.
- Passwords, auth tokens, session cookies, and other credentials are never collected.
- Raw free-text search queries, raw URLs with query strings, and direct stock mutation events are excluded from the allowlist.

---

## 7. Throttle and Debounce Strategy

- `backoffice_page_viewed`: Debounce rapid re-navigation to the same page in a short window (for example 2 seconds) to avoid duplicate page metrics from double-clicks or rapid tab switching.
- `page_load_measured`: Sample or throttle client-side load measurements, with full capture for slow pages and lower-rate sampling for normal loads.
- `api_request_failed`: Rate-limit repeated identical error bursts per endpoint and HTTP status so a single outage does not overwhelm the pipeline.
- `search_query_executed`: Only fired after the search action is submitted or resolved; client-side keystroke events are not recorded.

---

## 8. Event Categories

- Inventory: `inbound_order_created`, `outbound_order_created`, `stock_threshold_triggered`, `direct_stock_edit_rejected`, `inventory_discrepancy_detected`, `inventory_count_recorded`
- Security: `user_login_succeeded`, `user_login_failed`, `permission_denied`
- Errors: `api_request_failed`, `background_job_failed`
- Performance: `page_load_measured`, `search_query_executed`
- Navigation: `backoffice_page_viewed`, `order_creation_abandoned`, `report_export_requested`

---

## 9. Summary

This telemetry plan follows the authoritative TrackFlow requirements exactly: 16 total events, 5 mandatory inventory events, no direct-stock-write events, no carrier or recipient PII, and an envelope that is intentionally minimal and typed.
