# Dependencies & Infrastructure

- Add npm dependencies only when needed for the current task; prefer what Next.js and Tailwind already provide.
- Do not modify `infra/`, `services/`, or CI unless the task explicitly covers backend/deployment work.
- Do not run destructive git commands (`reset --hard`, `push --force`) unless the user explicitly requests them.
