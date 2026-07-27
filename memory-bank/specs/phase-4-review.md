# Phase 4 — Review Sign-off

**Date:** 2026-07-27  
**Reviewed:** Shared types (`packages/shared/types`), mock catalog (`uis/website/src/data/catalog.ts`), components under `uis/website/src/components/`, root `SiteLayout` wiring.  
**Against:** `specs/inventory.md`, `specs/decisions.md`, `specs/migration-process.md` § Phase 4.

---

## 4a. Data review — **Approved**

| Check | Result | Evidence |
|-------|--------|----------|
| Coverage | Pass | Inventory product/cart/checkout/site fields typed in `@repo/shared-types`. Hero campaign copy stays as component props (page content, not a second schema). |
| Categories | Pass | Catalog counts: footwear 4, shirts 8, pants 5, accessories 3. |
| Mock sufficiency | Pass | 20 catalog products; 4 new arrivals; 5 best sellers; featured PDP with details/materials/styling/image; 3 cart lines + 10% tax totals. |
| Single source | Pass | No local `interface Product` / `type Product` in `uis/website/src`. |
| Brand language | Pass | Maison Atelier Rue names; FR/EN mix; `SITE_CONTACT` matches D5. |
| Money | Pass | All mock `currency: "EUR"`; `formatPrice` / `computeCartTotals` used. |

### Explicit deferrals (named)

| Item | Reason |
|------|--------|
| Product preview modal payload | Deferred by D9 |
| Real search / auth / payment APIs | Out of scope (decisions non-goals) |
| Hero/campaign as typed entity | Page props only until CMS/backend |
| Checkout form controlled state | HTML fields match `Checkout*` types; wiring in Phase 5 |

---

## 4b. Component review — **Approved**

| Check | Result | Evidence |
|-------|--------|----------|
| Spec chrome | Pass | `Navbar` + `Footer` via `SiteLayout` in root layout |
| Decomposition | Pass | Inventory 1b blocks present (layout/home/catalog/product/cart/checkout). Preview modal deferred (D9). |
| Props | Pass | Product/cart components take `Product` / `CartLine` / shared helpers |
| A11y basics | Pass | Skip link; `nav`/`footer` landmarks; search label; filter labels; size `radiogroup`; bag `aria-label` |
| Visual tokens | Pass | Token colors + Manrope/Spectral; `nav-sleeve`, placeholders, rails from reference CSS |
| Scope | Pass | No auth, payment provider, or live API |

### Merge / split notes

| Note | Disposition |
|------|-------------|
| `CatalogDemo` / `CartDemo` | Smoke helpers only — not required on production routes; Phase 5 pages compose primitives directly |
| `CheckoutUpsell` / `RecommendedRail` | Not extracted yet; optional checkout merchandising — add in Phase 5 if the checkout view needs them |
| Blazers under `shirts` | Accepted under D6 four-category taxonomy (`categoryLabel` carries Blazer/Jacket) |

---

## Outcome

| Gate | Status |
|------|--------|
| 4a Data | **Approved** |
| 4b Components | **Approved** |
| Overall | **Approved — proceed to Phase 5** |

### Non-blocking follow-ups (Phase 5+)

1. Split smoke `/` into real routes: `/`, `/catalog`, `/product/[slug]`, `/cart`, `/checkout`.
2. Add per-route metadata + Home JSON-LD (SEO).
3. Optionally extract checkout upsell/recommended rails if parity requires them.
4. Wire cart count to shared client state (still mock) instead of layout constant.
5. Prefer `next/image` + remote patterns once image hosts are fixed.

**Exit met:** Both gates approved with named non-blocking follow-ups only.
