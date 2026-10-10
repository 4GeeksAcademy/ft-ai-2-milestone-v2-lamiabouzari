# AI Engineering Company Project — Student Template

[![4Geeks Academy](https://img.shields.io/badge/4Geeks-Academy-blue)](https://4geeksacademy.com)
[![AI Engineering](https://img.shields.io/badge/track-AI%20Engineering-green)](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)

_Base template for transversal projects in the AI Engineering Career Program — 4Geeks Academy._

> _Instrucciones disponibles en español en [README.es.md](./README.es.md)._

---

## Purpose

This repository is the **starter template** for transversal projects. You will work on real company scenarios (Brasaland, TrackFlow, Nexova), building deliverables that map to course milestones (Web, Programming, Backend, Telemetry, RAG, Agents, Workflows, Real-time).

- Create a template from this repository.
- Replace the placeholder `CONTEXT.md` with your assigned company context.
- Use `skills/` and the directory-level `README.md` files as working guidance.

---

## Current status of the template

The repository currently provides a **base folder structure and documentation skeleton**. It does not include runnable apps or global scripts yet.

- `CONTEXT.md` is a placeholder and must be replaced with your assigned company context.
- There is no root `AGENTS.md` yet.
- Shared package metadata exists in `packages/shared/package.json` (`@repo/shared-types`), but no workspace runner is configured at root.

---

## Repository structure

```text
ai-engineering-company-project-monorepo/
├── README.md
├── README.es.md
├── CONTEXT.md                # Placeholder to be replaced with assigned context
├── agents/                   # Agent patterns/templates and tools docs
├── data/                     # raw, process, pipelines, eval
├── docs/                     # Project and architecture documentation
├── infra/                    # Docker, Terraform, deployment configs
├── internal/                 # CLIs, packaged migration scripts, internal utilities
├── mcps/                     # Model Context Protocol (MCP) Servers
├── packages/
│   └── shared/               # Shared package (@repo/shared-types)
├── scripts/                  # Script conventions/documentation
├── services/                 # APIs and background workers
├── shared/                   # Shared assets/conventions at repo level
├── skills/                   # Reusable agent skills
├── uis/                      # User interfaces (React, Next.js, Streamlit, HTML)
└── workflows/                # Automation/orchestration documentation
```

---

## How to start

1. **Use this repository as a template** and create your own project repo.
2. **Clone** your repository (or open it in Codespaces).
3. **Replace** `CONTEXT.md` with the full context for your assigned company.
4. **Review** each top-level folder `README.md` to understand intended responsibilities (`uis/`, `services/`, `data/`, `skills/`, etc.).
5. **Start implementing** milestone deliverables in `uis/` and `services/`, reusing `packages/shared/` and `data/` as needed.

---

## Milestones (reference)

| Milestone | Focus        | Typical deliverables                        |
| --------- | ------------ | ------------------------------------------- |
| 0         | Prework      | Environment setup, first prompts            |
| 1         | Web          | Corporate website, forms, SEO               |
| 2         | Programming  | Business logic, scoring, calculations       |
| 3         | AI-driven UI | AI-generated interfaces                     |
| 4         | Next.js      | Portals, loyalty app, operations UI         |
| 5         | Backend      | Central API (locations, menus, sales, etc.) |
| 6         | Telemetry    | Data pipeline, dashboards                   |
| 7         | RAG & Memory | Semantic knowledge base, search             |
| 8         | Agents       | Support, onboarding, training agents        |
| 9         | Workflows    | n8n automations                             |
| 10        | Real-time    | Live dashboards, alerts, streaming          |

---

## Links

- [4Geeks Academy — AI Engineering](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)
- [How to start a coding project](https://4geeks.com/lesson/how-to-start-a-project)

---

## Contributors

This template was built as part of the 4Geeks Academy AI Engineering Career Program by [@marcogonzalo](https://www.linkedin.com/in/marcogonzalo) and [@alezanchezr](https://x.com/alesanchezr) and many other contributors. Find out more about our [AI Engineering Course](https://4geeksacademy.com/en/career-programs/ai-engineering), and [other courses](https://4geeksacademy.com/en/program-comparison).

You can find other templates and resources like this at the [4Geeks Academy GitHub page](https://github.com/4geeksacademy).

_This template is maintained by 4Geeks Academy for the AI Engineering track. For exclusive use in the programme._

## Message queues and asynchronous reporting tasks

The reporting pipeline is queued with Celery. Redis is the broker and result
backend, the API and worker run as separate processes, and Flower provides a
web dashboard at http://localhost:5555.

Set `REDIS_URL=redis://redis:6379/0` in the Compose environment (use
`redis://localhost:6379/0` when running directly on the host). Apply
`migrations/002_create_dlq_tasks.sql` to PostgreSQL before running the worker.

Start the services with:

```bash
docker compose up --build backend worker redis flower
```

Queue a report and poll its status:

```bash
curl -X POST 'http://localhost:8000/reporting/pipeline-runs'
curl 'http://localhost:8000/tasks/<task_id>'
```

The POST returns HTTP 202 and `{"task_id": "..."}` immediately. Stopping or
restarting FastAPI does not stop the independent Celery worker. Redis is
configured with the `noeviction` policy so queued messages are not silently
evicted.

Validation commands:

```bash
services/.venv/bin/pytest -q
python -m compileall services
docker compose config
git diff --check
```

## Supplier directory

Context source: [`CONTEXT-company.md`](CONTEXT-company.md) (TrackFlow supplier directory). Retail catalog currency in `packages/shared` stays EUR-only and is not the supplier currency rule.

### Fields and allowed values

- `name`, `country` (`USA` or `Spain`), `categories` (at least one of `carrier_last_mile`, `carrier_international`, `warehouse_supplies`, `packaging_materials`, `reverse_logistics`, `fleet_maintenance`, `it_and_wms_software`, `cleaning_and_facilities`)
- `rate_per_shipment`: finite and strictly greater than 0
- `currency`: `USD` when the country is `USA`, `EUR` when the country is `Spain`
- `status`: `active` or `suspended`
- `updated_at`: timezone-aware UTC timestamp generated by the API on create and on every rate change
- Optional: `service_zone`, `contact_email`, `notes`

### Database

TinyDB table `suppliers` only. `DATABASE_PATH` defaults to `data/db.json` relative to the process working directory. The API is started from `services/`, so the local file is `services/data/db.json`. Tests set `SUPPLIERS_SEED_ON_STARTUP=0` and use a temporary file. They do not open that local database.

### Commands

Working directory for every seed command: `services/`.

`services/pyproject.toml` declares the seed command and the packages it imports: `pydantic`, `pydantic-settings`, `email-validator`, `sqlmodel`, and `tinydb`. `tool.uv.managed` is `false`, so uv does not own `services/.venv` and `uv sync` must not be run there. A sync would remove the API packages that are already installed in that virtualenv.

The application virtualenv already has those packages. Install only the `seed` entry point into it, then run the command:

```text
cd services
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
uv run seed
```

`uv run seed` prints how many suppliers were inserted. The default database is `data/db.json` in the working directory (`services/data/db.json` when the API or seed is started from `services/`). Set `DATABASE_PATH` to use a different TinyDB file.

A separate clean virtualenv, created with `uv venv --python 3.12` and `uv pip install -e .` (dependencies included, not `--no-deps`), can run the same command without the application virtualenv:

```text
uv run --python <clean-venv>\Scripts\python.exe seed
```

That clean run printed `15` on an empty isolated file and `0` on the second run. The 14 installed packages came from the declared dependencies and their dependencies. It did not use the application virtualenv.

API, from `services/`:

```text
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Backoffice, from `uis/backoffice/`:

```text
npm run dev
```

The Suppliers page is http://localhost:3000/suppliers. The API base URL is the existing `NEXT_PUBLIC_API_URL` (default `/api/backend`).

Supplier tests, from `services/` so settings load from `services/.env`:

```text
.\.venv\Scripts\python.exe -m pytest ..\tests\test_suppliers.py -q
```

Backoffice checks, from `uis/backoffice/`:

```text
npm run lint
npm run build
```

### Endpoint examples

All supplier routes require the existing bearer token.

```text
POST /suppliers
GET /suppliers
GET /suppliers?country=Spain&category=carrier_international
GET /suppliers/{id}
PATCH /suppliers/{id}/rate
{"rate_per_shipment": 5.1}
PATCH /suppliers/{id}/status
{"status": "suspended"}
DELETE /suppliers/{id}
```

`POST` returns 201. Unknown ids return 404. Invalid fields return 422 and are not written. `DELETE` returns `{"id": <id>, "detail": "Supplier deleted."}`.

### Assignment checklist

| Requirement | Implementation |
| --- | --- |
| FastAPI module under `services/api`, same app on port 8000 | `services/api` mounted from `services/main.py` |
| Separate input and response schemas | `services/api/schemas.py` |
| TinyDB `suppliers` table, other tables left in place | `services/api/repository.py` |
| Idempotent seed and startup seed | `services/api/seed.py`; startup skips when `SUPPLIERS_SEED_ON_STARTUP=0` |
| List, country filter, category filter, and both together | `GET /suppliers` |
| Backoffice page, nav, filters, create, inline rate and status | `uis/backoffice/src/app/suppliers/page.tsx` |
| Isolated tests | `tests/test_suppliers.py` |

### Submission screenshots

The three required images are in `docs/supplier-directory/`. The seed and Swagger captures, and the Spain page capture, used an isolated TinyDB file. They did not read or write `services/data/db.json`.

1. `seed-terminal.png` — terminal in `services/`. `DATABASE_PATH` points at an isolated file. The first `uv run seed` printed `15`. The second printed `0`.
2. `swagger-filtered-response.png` — isolated API on port 8010. Authorized `GET /suppliers?country=Spain&category=carrier_international` returned HTTP 200 and only DHL Express España. The bearer token is not in the image.
3. `suppliers-spain.png` — signed-in Suppliers page against that same isolated API, with Country set to Spain and Category set to all categories. The directory shows the six Spanish suppliers, EUR rates, status badges, timestamps, and Edit rate / Edit status.
