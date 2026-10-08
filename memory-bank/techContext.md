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

Backoffice login is handled by the FastAPI app in `services/`. Accounts live in TinyDB, not Postgres. `DATABASE_PATH` defaults to `data/db.json` relative to the process working directory. The local API is started from `services/`, so the file in use is `services/data/db.json`. The repo-root `data/db.json` is a different file. `DATABASE_URL` points at Postgres for inventory, telemetry, RFP, and Support Agent chat sessions. Accounts stay in TinyDB.

The local demo account is `dev@example.com` with role `admin`. Its password is hashed with the existing bcrypt `CryptContext` in `services/routers/auth.py`.

## Development Requirements

- Reuse shared logic instead of duplicating it.
- Keep TypeScript types explicit.
- Keep components organized and reusable.
- Run lint and build validation before submission.
- Preserve the Maison Atelier Rue fashion and e-commerce identity.