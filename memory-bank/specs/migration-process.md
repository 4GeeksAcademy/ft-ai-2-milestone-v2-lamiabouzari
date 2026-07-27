# Migration Process Spec

Migrate **Maison Atelier Rue** from the static reference (`uis/website_v1/`) to a Next.js app (`uis/website/`) without redesigning the brand or inventing a second product schema.

**Sources of truth**

| Concern | Source |
|---------|--------|
| Views & UX requirements | `uis/website_v1/SPEC.md` |
| Visual / copy reference | `uis/website_v1/*.html`, `style.css` |
| Brand & domain | `company-choice.md` |
| Guardrails | `memory-bank/rules/` |

`uis/website_v1/` stays **read-only** unless a task explicitly changes it.

---

## Process overview

```text
0. Prepare
1. Inventory (pages → components → data)
2. Model data (shared types + mock catalog)
3. Extract components (shared chrome first)
4. ★ Review: data + components   ← gate before pages
5. Migrate views (one page at a time)
6. SEO & responsive QA
7. Close-out (checklist + memory bank)
```

Do not start view migration (phase 5) until the **Review** gate (phase 4) passes.

---

## Phase 0 — Prepare

1. Confirm target path: `uis/website/` (Next.js + TypeScript + Tailwind).
2. Scaffold the app if missing; wire workspace access to `@repo/shared-types`.
3. Port design tokens from `website_v1` (colors: `navbase`, `oat`, `clay`, `sleeve`, `stone`; fonts: Manrope / Spectral).
4. Note open questions in `memory-bank/project-context.md` (do not invent brand facts).

**Exit:** App runs (`npm run dev`); tokens available; no edits under `website_v1/`.

---

## Phase 1 — Inventory

Walk the reference and produce three lists (can live in this folder as working notes, or briefly in project-context):

### 1a. Pages

| Reference file | Target route | Spec view |
|----------------|--------------|-----------|
| `index.html` | `/` | Home |
| `catalog.html` | `/catalog` | Catalog |
| `product.html` | `/product/[slug]` | Product |
| `cart.html` | `/cart` | Cart |
| `checkout.html` | `/checkout` | Checkout |

### 1b. Components (candidates)

From repeated markup / distinct UI blocks:

- `Navbar` (logo, search, account, bag)
- `Footer` (categories, legal, contact)
- `Hero`
- `ProductCard` (horizontal lists + catalog grid)
- `ProductGrid` / horizontal `ProductRail`
- `FilterBar` (category, size)
- `CartLineItem`
- `CartSummary`
- `CheckoutSteps` (personal → shipping → payment)
- Page-level shells only where composition differs

### 1c. Data fields (from HTML, not guesswork)

Collect every product-facing field used in the reference, e.g.:

- identity: id / slug, name, product code
- merchandising: category, price, currency, image/alt, short blurb
- variants: available sizes
- detail: materials, recommended use
- cart: quantity, unit price, line total
- checkout: personal details, shipping address, card fields (UI only / mocked)

**Exit:** Inventory complete enough to drive types and component APIs.

---

## Phase 2 — Model data

1. Define shared types in `packages/shared/types/` (`Product`, `Category`, `CartLine`, checkout form shapes as needed).
2. Add a **mock catalog** (enough for Home rails, Catalog 4×5 reference, Product detail, Cart with **3 sample lines**).
3. No real API, DB, or payment provider in this phase.
4. Import types from `@repo/shared-types` only — no duplicate local interfaces in the UI app.

**Exit:** Types compile; mock data covers all five views’ content needs.

---

## Phase 3 — Extract components

1. Implement shared chrome first: `Navbar`, `Footer` → app layout.
2. Implement catalog/commerce primitives: `ProductCard`, filters, cart/checkout pieces.
3. Props must use shared types; avoid hardcoding product fields inside components.
4. Match reference structure and tokens; no redesign unless asked.

**Exit:** Components render in isolation or Story-less smoke pages; layout shell works.

---

## Phase 4 — Review gate (data + components) ★

**Required before migrating individual views.** Treat failures as blockers.

### 4a. Data review

| Check | Pass criteria |
|-------|----------------|
| Coverage | Every field from inventory 1c is typed or explicitly deferred |
| Categories | Footwear, shirts, pants, accessories represented |
| Mock sufficiency | Home (new + bestsellers), Catalog (~20), Product detail, Cart (3 lines) covered |
| Single source | No second product schema inside `uis/website/` |
| Brand language | Names/copy tone match Maison Atelier Rue (FR/EN mix OK) |
| Money | Price + currency consistent with reference (prefer EUR where shown) |

**Data review outcomes:** Approve · Request changes · Defer field (named + reason)

### 4b. Component review

| Check | Pass criteria |
|-------|----------------|
| Spec chrome | Navbar + Footer reusable; used by layout for all routes |
| Decomposition | Distinct blocks from inventory 1b exist as components (or justified merge) |
| Props | Driven by shared types / mock data, not copy-pasted literals for catalog items |
| A11y basics | Landmarks, labels for search/filters/size, meaningful link text |
| Visual tokens | Colors/type/spacing align with `website_v1` |
| Scope | No premature auth, payments API, or backend wiring |

**Component review outcomes:** Approve · Request changes · Merge/split note

### 4c. Sign-off

Record briefly in `memory-bank/project-context.md` (or a short note under `specs/`):

- Date / what was reviewed
- Pass / fail per 4a and 4b
- Open follow-ups

**Exit:** Both data and components **Approved** (or approved with named, non-blocking follow-ups).

---

## Phase 5 — Migrate views

Migrate **one view per change set** when practical. For each view:

1. Map sections from `SPEC.md` + reference HTML.
2. Compose from approved components + mock data.
3. Preserve SEO basics present in the reference (title, meta description, semantic headings; JSON-LD where Home has it).
4. Verify against the view checklist below before moving on.

| View | Must have |
|------|-----------|
| Home | Hero, New arrivals rail, Best sellers rail, layout chrome |
| Catalog | Filter bar (category + size), ~4×5 product grid |
| Product | Image ~½ width, name/code/size/price/qty/add-to-cart, materials + use |
| Cart | Full page, line items, summary (subtotal/tax/total), Purchase CTA, 3 samples |
| Checkout | 3 steps: personal → shipping → card |

**Exit:** All five routes render with parity against the view table.

---

## Phase 6 — SEO & responsive QA

1. Semantic structure and indexable content across routes.
2. Breakpoints: ~375px, ~768px, ~1280px — no overflow, readable hierarchy.
3. Shared chrome consistent on every page.
4. Spot-check reduced-motion if animations were ported.

**Exit:** QA notes clean enough to call migration visually complete for the milestone.

---

## Phase 7 — Close-out

1. Tick items in `memory-bank/project-context.md` migration checklist.
2. Update `architecture.md` if folder/scripts/types changed.
3. Run verification from `memory-bank/rules/verification.md`.
4. Do not delete or “replace in place” `website_v1/`.

---

## Anti-patterns

- Editing `website_v1/` to match the new app
- Building all pages before the data/component review gate
- Local `interface Product` duplicates in the Next.js app
- Redesigning palette/layout under the guise of “migration”
- Wiring real payment or inventory APIs in this milestone
