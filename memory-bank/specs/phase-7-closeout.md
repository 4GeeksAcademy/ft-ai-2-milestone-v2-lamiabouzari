# Phase 7 — Close-out

**Date:** 2026-07-27  
**Milestone:** Maison Atelier Rue static → Next.js migration

## Verification (`rules/verification.md`)

| # | Check | Result |
|---|-------|--------|
| 1 | `npm run build` / TypeScript | Pass |
| 2 | Views match SPEC sections (Home, Catalog, Product, Cart, Checkout) | Pass — Phase 5–6 |
| 3 | `uis/website_v1/` untouched (reference intact) | Pass |
| 4 | `@repo/shared-types` imports; no local Product schema | Pass |
| 5 | Memory bank updated | Pass (this file + project-context) |
| — | `npm run lint` | Pass |

## Delivered

- Next.js 16 app at `uis/website/` with shared layout chrome
- Five routes with mock catalog, EUR pricing, SPEC category taxonomy
- Shared types in `packages/shared`
- Specs: inventory, decisions, phase-4 review, phase-6 QA

## How to run

```bash
cd uis/website
npm run dev      # http://localhost:3000
npm run build
npm run start
```

## Out of scope (by design)

- Real payment / auth / inventory APIs
- Catalog preview modal (D9)
- Replacing or deleting `website_v1/`

**Migration process complete** through Phase 7.
