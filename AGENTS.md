# AGENTS.md

## Startup Instructions

Before making changes, always review:

1. `memory-bank/projectbrief.md`
2. `memory-bank/techContext.md`
3. `memory-bank/progress.md`

## Development Workflow

1. Read the Memory Bank.
2. Understand the requested task.
3. Reuse existing shared logic whenever possible.
4. Validate changes before committing.

## Protected Areas

Do not remove or duplicate existing business logic without explicit approval.

## Validation

Before opening a Pull Request:

- Run `npm run lint`
- Run `npm run build`
- Verify the public website routes.
- Verify the backoffice application loads correctly.