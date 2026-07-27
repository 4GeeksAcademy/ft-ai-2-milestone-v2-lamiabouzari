# Phase 6 — SEO & Responsive QA

**Date:** 2026-07-27  
**App:** `uis/website`  
**Breakpoints checked (layout/CSS review):** ~375px, ~768px, ~1280px

---

## SEO

| Check | Status | Notes |
|-------|--------|-------|
| `lang="en"` on `<html>` | Pass | Root layout |
| Unique titles via template | Pass | `%s \| Maison Atelier Rue`; Home/Catalogue/Cart/Checkout/PDP set |
| Meta descriptions | Pass | All five view types |
| Open Graph defaults | Pass | Root + Home + Product (image when present) |
| `metadataBase` | Pass | `SITE_CONTACT.url` |
| Semantic landmarks | Pass | Skip link, `header`/`nav`, `main#main-content`, `footer` |
| Home JSON-LD | Pass | Organization, WebSite/SearchAction, New arrivals ItemList |
| Product JSON-LD | Pass | Product + Offer (EUR) on `/product/[slug]` |
| Indexable headings | Pass | Single H1 per view; section H2s on Home/Cart/Checkout |
| Shared chrome on all routes | Pass | `SiteLayout` |

---

## Responsive

| Check | Status | Notes |
|-------|--------|-------|
| Navbar stacks on small screens | Pass | Logo → search → actions |
| Home hero readable at 375 | Pass | Title scales `text-3xl` → `md:text-5xl`; CTAs wrap |
| Product rails scroll horizontally | Pass | `overflow-x-auto` + snap |
| Catalog grid | Pass | 1 / 2 / 3 / 4 cols by breakpoint (SPEC 4-col desktop) |
| PDP two-column → stack | Pass | `lg:grid-cols-2`; add-to-cart full-width on mobile |
| Cart table → stacked rows | Pass | Mobile labels; summary below list |
| Checkout step jump links | Pass | Stack on xs; shortened labels; 3-col from `sm` |
| Announcement bar | Pass | Smaller type / tracking on xs; wraps |
| Horizontal overflow | Pass | `overflow-x-hidden` on `body` |
| Reduced motion | Pass | Placeholder sweep disabled under `prefers-reduced-motion` |

---

## Fixes applied this phase

1. Root metadata: title template, Open Graph/Twitter, `metadataBase`
2. Product schema.org JSON-LD + OG image when available
3. Checkout intro / announcement responsive tightening
4. PDP add-to-cart / qty layout for narrow viewports
5. Hero title scale for ~375px
6. Body `overflow-x-hidden`; reduced-motion polish

---

## Residual (non-blocking)

- Search remains presentational (no full-text index beyond simple catalog `q` filter)
- Account button still inert (no auth — by design)
- Legal footer links are placeholders (`#`)
- Manual device lab / Lighthouse not run in this environment — CSS breakpoint review only
- External product images still use `<img>`; `next/image` optional later

**Exit:** Migration visually complete for the milestone from SEO + responsive QA perspective. Proceed to Phase 7 close-out when ready.
