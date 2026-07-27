# Project Architecture

**Status:** Static → Next.js migration complete (Phases 0–7). See `memory-bank/specs/phase-7-closeout.md`.

## Tech Stack

- Next.js 16 (App Router) + TypeScript in `uis/website/`
- Tailwind CSS v4 — brand tokens in `uis/website/src/app/globals.css`
- Fonts: Manrope (sans) + Spectral (serif) via `next/font/google`
- Shared types via `packages/shared` (`@repo/shared-types`, file dependency + `transpilePackages`)

## Scripts (`uis/website/`)

| Command | Purpose |
|---------|---------|
| `npm run dev` | Local dev server |
| `npm run build` | Production build |
| `npm run start` | Serve production build |
| `npm run lint` | ESLint |

`next.config.ts` sets `turbopack.root` / `outputFileTracingRoot` to the monorepo root so `@repo/shared-types` resolves outside `uis/website/`.

## Folder Layout

```text
uis/
  website_v1/           # Legacy static reference (read-only — preserved)
  website/              # Next.js target app (migration deliverable)
    src/app/            # Routes: /, /catalog, /product/[slug], /cart, /checkout
    src/components/     # layout, home, catalog, product, cart, checkout
    src/data/catalog.ts # Mock catalog
packages/
  shared/
    index.ts            # Package entry
    types/index.ts      # Shared retail types — single schema source
memory-bank/            # Context, specs, rules
```

## Components (Phase 3)

| Area | Components |
|------|------------|
| Layout | `SkipLink`, `Navbar`, `Footer`, `SiteLayout` |
| Home | `Hero`, `EditorialDivider`, `ProductRail` |
| Catalog | `CatalogIntro`, `FilterBar`, `ProductGrid`, `EmptyFilterState`, `CatalogDemo` |
| Product | `ProductCard`, `ProductGallery`, `ProductInfo`, `ProductDetailTabs`, `StylingSuggestions`, `RelatedProducts` |
| Cart | `CartHeader`, `CartLineItem`, `CartSummary`, `CartDemo` |
| Checkout | `AnnouncementBar`, `CheckoutIntro`, `CheckoutSteps`, `CheckoutOrderSummary` |

Preview modal deferred (D9). Props use `@repo/shared-types` — no local product interfaces.

## Routes (Phase 5)

| Route | Page |
|-------|------|
| `/` | Home — Hero, rails, JSON-LD |
| `/catalog` | Filters + 4-col grid (`?category=` / `?size=` / `?q=`) |
| `/product/[slug]` | PDP (SSG via `generateStaticParams`) + Product JSON-LD |
| `/cart` | 3 sample lines + summary |
| `/checkout` | 3-step form + order summary + recommended |

## Design tokens (ported)

`navbase`, `navtext`, `sleeve`, `oat`, `clay`, `stone`, `ink` — plus page atmosphere gradients from `website_v1/style.css`.

## Product Data Model

Types live in `packages/shared/types/index.ts` (`Product`, `CartLine`, checkout shapes, `SITE_CONTACT`, `formatPrice`, `computeCartTotals`).

Mock catalog: `uis/website/src/data/catalog.ts` — imports types from `@repo/shared-types` only.

| Export | Purpose |
|--------|---------|
| `catalogProducts` | 20 items for catalog grid |
| `newArrivals` / `bestSellers` | Home rails |
| `featuredProduct` | Full PDP (`veste-de-bureau-marine`) |
| `sampleCartLines` | 3 cart lines |

**Note:** Blazers/jackets use `category: "shirts"` with a Blazer/Jacket `categoryLabel` under the locked 4-category taxonomy (D6).

## Company

- Brand: **Maison Atelier Rue** — see `company-choice.md`
- Categories: `footwear` | `shirts` | `pants` | `accessories` (see `specs/decisions.md` D6)
- Currency: **EUR**
- Locale tone: mixed French–English; Paris contact from Home footer is canonical

## Related Specs

- Migration process: `memory-bank/specs/migration-process.md`
- Inventory: `memory-bank/specs/inventory.md`
- Decisions: `memory-bank/specs/decisions.md`
- Phase 4 review: `memory-bank/specs/phase-4-review.md`
- Phase 6 QA: `memory-bank/specs/phase-6-qa.md`
- Phase 7 close-out: `memory-bank/specs/phase-7-closeout.md`
- View requirements: `uis/website_v1/SPEC.md`
- Visual reference: `uis/website_v1/index.html`, `style.css`
