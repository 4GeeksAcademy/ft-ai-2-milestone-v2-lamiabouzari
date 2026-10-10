# Technical Context

## Technology Stack

- Next.js
- React
- TypeScript
- ESLint
- Node.js and npm
- Git and GitHub Codespaces

## Repository Structure

- `uis/website` contains the public Maison Atelier Rue website.
- `uis/backoffice` contains the internal company application.
- `packages/shared` contains reusable shared types and business logic.
- `services` is reserved for APIs and background services.
- `memory-bank` stores persistent business and technical context.
- `.agents` stores development-agent rules and reusable skills.

## Application Routes

The public website includes:

- `/`
- `/catalog`
- `/product/[slug]`
- `/cart`
- `/checkout`

## Local authentication

Backoffice login is handled by the FastAPI app in `services/`. Accounts live in TinyDB, not Postgres. `DATABASE_PATH` defaults to `data/db.json` relative to the process working directory. The local API is started from `services/`, so the file in use is `services/data/db.json`. The repo-root `data/db.json` is a different file. `DATABASE_URL` points at Postgres for inventory, telemetry, RFP, and Support Agent chat sessions. The SQLAlchemy engine keeps a small pool and checks connections before reuse. Chat token text is queued onto that pool instead of opening a connection for every delta. Accounts stay in TinyDB.

The local demo account is `dev@example.com` with role `admin`. Its password is hashed with the existing bcrypt `CryptContext` in `services/routers/auth.py`. Incident Analysis must send that same bearer token; `/api/incidents` rejects a request with no `Authorization` header. The `/incidents` page has Incident Manager and CSV Analysis tabs. CSV Analysis posts the uploaded file to `POST /api/incidents/analyze`. The latest aggregate report, filename, and timestamp are stored in the TinyDB table `incident_analysis_reports` and reloaded from `GET /api/incidents/analysis`. Raw CSV rows are not stored.

## Knowledge retrieval

Company policy lives in the four Markdown files under `docs/company-knowledge-base/` and is indexed by `python -m data.process.rag`. Retrieval keeps chunks at or above score 0.25. When `OPENAI_API_KEY` is unset, indexing uses a normalized bag-of-words vector over those documents' own vocabulary in the Qdrant collection `trackflow_knowledge`, and answers are the retrieved section text after the existing business safeguards. When the key is set, embedding and generation use the configured OpenAI-compatible models, and those vectors are stored in `trackflow_knowledge_provider` so the local index is not replaced. A question with no supporting chunk still receives the safe refusal.

## Weekly reporting

`GET /reporting/weekly-warehouse-client-performance` reads `reporting.weekly_warehouse_client_performance` and the latest `reporting.pipeline_runs` row. No recorded run is `never_run`. A completed run with `records_processed` 0 is `completed_without_rows`. KPI rows require both `tags.warehouse` and `tags.client_id`. The pipeline reads `telemetry_events` and writes only the `reporting` schema.

## Development Requirements

- Reuse shared logic instead of duplicating it.
- Keep TypeScript types explicit.
- Keep components organized and reusable.
- Run lint and build validation before submission.
- Preserve the Maison Atelier Rue fashion and e-commerce identity.