# RFP intake

TrackFlow Sales uploads one client PDF in the backoffice. The existing FastAPI service stores the file under `data/raw/rfp/` and inserts one SQLModel ticket with status `analyzing`. Intake then runs in a background task. The page polls `GET /rfp/tickets`.

Part 1 statuses are only `analyzing` → `intake_complete`, or `analyzing` → `discarded`. An unexpected processing error keeps status `analyzing`, sets `intake_failed`, and stores `error_message`. The handoff stays not ready. The backoffice shows that failure and stops treating the ticket as in progress.

The PDF is converted to Markdown with MarkItDown before the classifier, orchestrator, workers, or synthesizer read it. Those are separate agents. They share one structured-output boundary. Without `RFP_INTAKE_LLM=1`, that boundary runs locally so routing stays deterministic. With the flag, it uses the same OpenAI-compatible gateway as RAG (`RFP_INTAKE_MODEL`, otherwise `RAG_GENERATION_MODEL`).

Departments:

| Key | Name | Contact |
|-----|------|---------|
| warehouse | Warehouse Operations | Ana Whitfield |
| lastmile | Last Mile and Carrier Management | Carlos Vega |
| reverse | Reverse Logistics | Sofía Ramos |

Workers may only restate figures present in the document. Missing volume, deadline, or budget becomes an open question.

## Part 2 handoff

When status is `intake_complete`, `rfp_tickets.handoff_ready` is true and `routing_handoff` holds contract `trackflow.rfp.intake.v1`:

- `ticket_id`
- `currency_context`
- `synthesizer` (sales summary and per-department asks)
- `sections` (department, contact, `key_aspects`, `open_questions`)

Discarded tickets leave `handoff_ready` false. No second API is created for Part 2.
