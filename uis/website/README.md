# Maison Atelier Rue — Next.js app

Migrated from `uis/website_v1` (static reference, preserved read-only).

## Scripts

```bash
npm run dev    # http://localhost:3000
npm run build
npm run start
npm run lint
```

## Routes

| Path | View |
|------|------|
| `/` | Home |
| `/catalog` | Catalog |
| `/product/[slug]` | Product detail |
| `/cart` | Cart |
| `/checkout` | Checkout |

## Notes

- Shared types: `@repo/shared-types` → `packages/shared`
- Design tokens: `src/app/globals.css`
- Mock catalog: `src/data/catalog.ts`
- Decisions: `memory-bank/specs/decisions.md`
- Migration close-out: `memory-bank/specs/phase-7-closeout.md`
