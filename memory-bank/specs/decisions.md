# Migration Decisions

Resolved conflicts from Phase 1 inventory. These bind Phase 2+ (types, mock data, components, views).

| # | Topic | Decision | Rationale |
|---|--------|----------|-----------|
| D1 | Product URL | `/product/[slug]` | SEO-friendly; `code` stays a separate display SKU. `slug` is kebab-case from the product name (stable, unique). |
| D2 | Product identity | `id` (string) + `slug` + `code` | `id` is the stable key for cart/relations; `slug` for routes; `code` for UI (e.g. `AR-FB-2407`). Prefer generating `id`/`slug` in mock data when the HTML had none. |
| D3 | Currency | **EUR** only | Paris brand; Home + Checkout + `company-choice.md` use EUR. Drop `$`/USD from Catalog/Cart/Product displays. Store `price` as a number (major units, e.g. `245`) + `currency: "EUR"`. Format as `EUR 245` or `EUR 245.00` to match Home. |
| D4 | Tax | Keep **10%** cart tax for mock totals | Matches `cart.html` script (`TAX_RATE = 0.1`). Document as mock FR simplification, not legal advice. |
| D5 | Contact / brand site | **Home footer is canonical** | Email `bonjour@maisonatelierrue.example`, phone `+33 1 00 45 67 89`, address `14 Rue de la Tranquillité, Paris`, URL `https://maisonatelierrue.example`. Ignore Checkout’s `atelier-row.fr` / Archives address. |
| D6 | Category taxonomy | SPEC/footer set: `footwear` \| `shirts` \| `pants` \| `accessories` | Align filters, footer links, and `Product.category`. Map old catalog values: `shoes` → `footwear`; `mens-shirts` / `womens-shirts` → `shirts`. Ensure mock catalog includes **pants**. Optional display label (e.g. “Men's Shirt”) may live on `categoryLabel` without becoming a filter id. |
| D7 | Size filters | Keep union of apparel + shoe + one-size | Filter options: `xs`–`xl`, `38`–`44`, `one-size` (plus product detail `xxs`–`xxl` where shown). A product exposes `sizes: string[]`; catalog card may show one representative size for the badge. |
| D8 | Shared chrome | **Full Navbar + Home-style Footer on every route** | SPEC requires reuse. Catalog’s minimal footer and missing Product/Cart footers are reference gaps — do not copy them. |
| D9 | Catalog preview modal | **Defer** (out of scope for migration parity) | Present in Catalog JS only; not in `SPEC.md`. Cards navigate to `/product/[slug]` instead. Revisit later if needed. |
| D10 | Catalog grid | Aim for **20 products**; prefer **4 columns × 5 rows** on desktop | SPEC says 4×5; reference used `xl:grid-cols-5`. Prefer SPEC layout for the Next.js app. |

## Mapping cheat sheet (old catalog → new)

| Reference `data-category` | New `category` |
|---------------------------|----------------|
| `mens-shirts` | `shirts` |
| `womens-shirts` | `shirts` |
| `shoes` | `footwear` |
| `accessories` | `accessories` |
| _(missing)_ | `pants` — add in mock data |

## Explicit non-goals (for now)

- Real payment processing
- Real search backend (search UI may remain presentational)
- Account auth
- Product preview modal
- Dual-currency support
