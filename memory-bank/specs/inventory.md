# Phase 1 — Migration Inventory

Source: `uis/website_v1/` (read-only). Enough to drive Phase 2 types and Phase 3 component APIs.

---

## 1a. Pages

| Reference file | Target route | Spec view | SEO / notes from reference |
|----------------|--------------|-----------|----------------------------|
| `index.html` | `/` | Home | Title + meta description; JSON-LD (Organization, WebSite/SearchAction, New arrivals ItemList); skip link |
| `catalog.html` | `/catalog` | Catalog | Title only (“Catalogue View”); filter UI + ~20 cards; client filter script; **simplified footer** (not full Home footer) |
| `product.html` | `/product/[slug]` | Product | Weak title (“Tailwind CDN Starter”); no meta description; **no footer**; related “From the catalog” grid |
| `cart.html` | `/cart` | Cart | Title only; line items via JS template + 3 samples; **no footer** |
| `checkout.html` | `/checkout` | Checkout | Title + meta description; announcement bar; 3-step form; order summary aside; full-ish footer (contact differs from Home) |

**Route decision:** `/product/[slug]` with separate `id` + `code` — see [`decisions.md`](./decisions.md) D1–D2.

---

## 1b. Components (candidates)

### Shared chrome (every route should use these after migration)

| Component | Present on | Contents |
|-----------|------------|----------|
| `SkipLink` | Home, Checkout | “Skip to main / checkout” |
| `Navbar` | All 5 | Logo (Maison / Atelier Rue), search form (`q`), Account button, bag link → `/cart`; Catalog also has optional `cart-count` badge |
| `Footer` | Home (canonical), Checkout (variant), Catalog (minimal) | Brand blurb; Categories (Footwear, Shirts, Pants, Accessories); Legal (Terms, Privacy, About); Contact (email, phone, address). Checkout adds Social. **Normalize on Home’s footer** for layout reuse. |

### Home-only

| Component | Contents |
|-----------|----------|
| `Hero` | Eyebrow (“Spring Campaign”), headline, body, primary/secondary CTAs; optional featured-set card (“Le Bureau Doux”) |
| `EditorialDivider` | Decorative divider between hero and rails |
| `ProductRail` | Section title + “View all” + horizontal scroll of `ProductCard`s (New arrivals, Best sellers) |

### Catalog

| Component | Contents |
|-----------|----------|
| `CatalogIntro` | Eyebrow, H1 “Products”, short blurb |
| `FilterBar` | Category `<select>`, size `<select>` |
| `ProductGrid` | Responsive grid of catalog `ProductCard`s |
| `EmptyFilterState` | “No products match…” |
| `ProductPreviewModal` (optional / defer) | Catalog click opens overlay with image, name, description, price, “Add to bag” — **not in SPEC.md**; flag for review |

### Product

| Component | Contents |
|-----------|----------|
| `ProductGallery` | Primary image (~½ width) |
| `ProductInfo` | Brand line, name, price, short description, product code, size radios, qty, Add to cart |
| `ProductDetailTabs` | “Product details” list + “Materials” list |
| `StylingSuggestions` | Recommended-use / styling copy (maps to SPEC “recommended use”) |
| `RelatedProducts` | “From the catalog” grid of compact cards |

### Cart

| Component | Contents |
|-----------|----------|
| `CartHeader` | Title + “Continue shopping” |
| `CartLineItem` | Thumbnail, name, ref/code, unit price, qty input, line total |
| `CartSummary` | Subtotal, Tax (10% in reference), Total, Purchase → `/checkout` |

### Checkout

| Component | Contents |
|-----------|----------|
| `AnnouncementBar` (optional) | Promo strip (free shipping copy) |
| `CheckoutIntro` | Title + step jump links (01/02/03) |
| `CheckoutSteps` | Step 1 personal, Step 2 shipping, Step 3 payment |
| `CheckoutOrderSummary` | Line names + prices + order total |
| `CheckoutUpsell` / `RecommendedRail` | “You may also like” + “Complete your look” cards |

### Layout shell

| Component | Role |
|-----------|------|
| `SiteLayout` | SkipLink + Navbar + `{children}` + Footer |

---

## 1c. Data fields (from HTML only)

### Product / catalog (appears across Home, Catalog, Product, Cart, Checkout)

| Field | Where seen | Notes |
|-------|------------|-------|
| `name` | All product UIs | e.g. “Rive Left-Bank Blazer”, “Veste de Bureau - Marine” |
| `shortDescription` / blurb | Home cards, Catalog cards, Product preview | One-line material/fit copy |
| `price` | All | Numeric; **display currency inconsistent** (EUR / `$` / USD formatter) |
| `currency` | Implied by display | Home/Checkout often `EUR`; Catalog/Cart/Product often `$` / USD |
| `image` + `imageAlt` | Product, Cart, Catalog (JS overlays), related grids | Home often uses CSS `placeholder-block` only |
| `category` | Catalog `data-category` | Values: `mens-shirts`, `womens-shirts`, `shoes`, `accessories` — **differs from footer labels** (Footwear, Shirts, Pants, Accessories) |
| `categoryLabel` | Catalog card eyebrow | e.g. “Men's Shirt”, “Shoes”, “Accessory” |
| `size` (single display / filter) | Catalog `data-size` + badge | `xs`–`xl`, `38`–`44`, `one-size` |
| `sizes` (available options) | Product size radios | `xxs`–`xxl` |
| `code` / `ref` | Product (`AR-FB-2407`), related cards (`Code AR-SH-101`), Cart (`REF-LN-2104`) | Naming varies: code vs ref |
| `details` (bullet list) | Product “Product details” tab | Fit/construction bullets |
| `materials` (bullet list) | Product “Materials” tab | Fiber + care |
| `stylingSuggestions` / recommended use | Product styling section | Long prose |
| `listTags` | Home JSON-LD / rails | “New arrivals”, “Best sellers”; Checkout cards use “New arrival”, “Best seller”, etc. |
| `id` | Cart samples only (`1`,`2`,`3`) | Not on most static cards — **must invent stable ids in Phase 2** from code/slug |

### Merchandising / campaign (Home)

| Field | Example |
|-------|---------|
| Campaign eyebrow | “Spring Campaign” |
| Hero headline / body | Copy on Home |
| Featured set title / body | “Le Bureau Doux” |
| CTA labels / hrefs | Shop campaign → catalog; lookbook → product |

### Cart line / summary

| Field | Where |
|-------|-------|
| `quantity` | Cart line, Product qty input |
| `unitPrice` | Cart |
| `lineTotal` | Cart (derived) |
| `subtotal`, `tax`, `total` | Cart summary; tax rate **0.10** in script |
| `taxRate` | Cart script constant |

### Checkout — personal

`firstName`, `lastName`, `email`, `phone` (optional)

### Checkout — shipping

`street`, `unit` (optional), `postalCode`, `city`, `country` (FR/BE/CH/LU options)

### Checkout — payment (UI only / mocked)

`cardName`, `cardNumber`, `expiry`, `cvc`

### Checkout — summary lines (static samples)

Line `name` + `price`; order total display

### Brand / site (footer, JSON-LD)

| Field | Canonical (prefer Home) | Conflict |
|-------|-------------------------|----------|
| Brand name | Maison Atelier Rue | — |
| Email | `bonjour@maisonatelierrue.example` | Checkout: `bonjour@atelier-row.fr` |
| Phone | `+33 1 00 45 67 89` | Checkout: `+33 1 44 00 12 21` |
| Address | `14 Rue de la Tranquillite, Paris` | Checkout: `12 Rue des Archives, Paris` |
| Site URL | `https://maisonatelierrue.example` | — |

### Filter option sets (Catalog) — **superseded by decisions**

Canonical options are in [`decisions.md`](./decisions.md) (D6, D7):

- **Categories:** `all` + `footwear` | `shirts` | `pants` | `accessories`
- **Sizes:** `all` + `xs`–`xl`, `38`–`44`, `one-size` (product detail may also use `xxs`/`xxl`)

### Spec vs reference gaps — **resolved**

| Gap | Resolution |
|-----|------------|
| Footer vs catalog category labels | Use SPEC/footer taxonomy (D6) |
| Catalog 4×5 vs `xl:grid-cols-5` | Prefer SPEC 4×5 on desktop (D10) |
| Missing footers on Product/Cart | Full shared Footer everywhere (D8) |
| EUR vs `$` | EUR only (D3) |
| Contact mismatches | Home footer canonical (D5) |
| Preview modal | Defer (D9) |
| Product URL / ids | `/product/[slug]` + `id`/`code` (D1, D2) |

See [`decisions.md`](./decisions.md) for full table.

---

## Counts for Phase 2 mock data

| Surface | Minimum mock content |
|---------|----------------------|
| Home New arrivals | 4 products |
| Home Best sellers | 4 products |
| Catalog grid | 20 products (can overlap Home); include all four categories |
| Product detail | ≥1 full product (slug, code, sizes, details, materials, styling, image) |
| Cart | **3** line items |
| Checkout summary | 3 lines (can match cart samples) |

---

## Exit checklist

- [x] Pages mapped to routes  
- [x] Components listed from repeated / distinct blocks  
- [x] Data fields collected from HTML (no invented backend fields)  
- [x] Conflicts resolved — see [`decisions.md`](./decisions.md)  

**Next:** Phase 2 — shared types + mock catalog in `packages/shared` / app mock module.
