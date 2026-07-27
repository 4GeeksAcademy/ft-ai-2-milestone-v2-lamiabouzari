# Static Site Migration Project

We are migrating the **Maison Atelier Rue** static site at `uis/website_v1` to a modern Next.js website in `uis/website/`.

Company choice and brand challenges: [`company-choice.md`](../company-choice.md).

## Additional Notes

- Distinct elements of the website must be converted into reusable components.
- This will have a backend at some point, so we need a placeholder product data model in `packages/shared/types/`.
- Domain language stays retail e-commerce (products, cart, orders) — see [rules/brand-alignment.md](./rules/brand-alignment.md).
- **Migration process:** [specs/migration-process.md](./specs/migration-process.md) (includes data + component review gate before page work).
- **Safety rules:** see [rules/](./rules/README.md) before continuing development.

## Status

**Migration complete (Phases 0–7).** Close-out: [`specs/phase-7-closeout.md`](./specs/phase-7-closeout.md).

Run the app: `cd uis/website && npm run dev`

| Spec | Link |
|------|------|
| Process | [specs/migration-process.md](./specs/migration-process.md) |
| Inventory | [specs/inventory.md](./specs/inventory.md) |
| Decisions | [specs/decisions.md](./specs/decisions.md) |
| Phase 4 review | [specs/phase-4-review.md](./specs/phase-4-review.md) |
| Phase 6 QA | [specs/phase-6-qa.md](./specs/phase-6-qa.md) |
| Phase 7 close-out | [specs/phase-7-closeout.md](./specs/phase-7-closeout.md) |

### Locked decisions (summary)

- Routes: `/product/[slug]`; identity = `id` + `slug` + `code`
- Money: **EUR** only; cart tax mock **10%**
- Contact: Home footer canonical (`maisonatelierrue.example`, 14 Rue de la Tranquillité)
- Categories: `footwear` | `shirts` | `pants` | `accessories`
- Chrome: full Navbar + Footer on every page
- Defer Catalog preview modal; cards link to product pages
- Catalog desktop grid: prefer SPEC **4×5**

### Artifacts

- Types: `packages/shared/types/index.ts`
- Mock catalog: `uis/website/src/data/catalog.ts`
- Components: `uis/website/src/components/{layout,home,catalog,product,cart,checkout}/`
- Routes: `uis/website/src/app/{page,catalog,product/[slug],cart,checkout}/`
- Reference (read-only): `uis/website_v1/`

## Migration Checklist

- [x] Phase 0 — Prepare (Next.js scaffold + tokens)
- [x] Phase 1 — Inventory (pages, components, data fields)
- [x] Resolve inventory conflicts ([`specs/decisions.md`](./specs/decisions.md))
- [x] Phase 2 — Model data (shared types + mock catalog)
- [x] Phase 3 — Extract components
- [x] Phase 4 — ★ Review: data + components (gate) — Approved
- [x] Phase 5 — Migrate views
- [x] Phase 6 — SEO & responsive QA
- [x] Phase 7 — Close-out (memory bank + verification)
- [x] Next.js app scaffolded in `uis/website/`
- [x] Shared layout (navbar + footer)
- [x] Home
- [x] Catalog (category + size filters, 4×5 grid)
- [x] Product detail
- [x] Cart (3 sample products)
- [x] Checkout (3-step flow)
- [x] SEO parity with reference
- [x] Responsive QA (mobile / tablet / desktop)
