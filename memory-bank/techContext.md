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

## Development Requirements

- Reuse shared logic instead of duplicating it.
- Keep TypeScript types explicit.
- Keep components organized and reusable.
- Run lint and build validation before submission.
- Preserve the Maison Atelier Rue fashion and e-commerce identity.