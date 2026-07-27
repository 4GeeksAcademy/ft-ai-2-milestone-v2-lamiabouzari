# Brand Alignment (Maison Atelier Rue)

Company context lives in `company-choice.md` and the static reference at `uis/website_v1/`. Binding decisions: `memory-bank/specs/decisions.md`.

When adding domain language or backend work:

- Reuse brand and catalog language: products, categories (`footwear`, `shirts`, `pants`, `accessories`), sizes, SKUs/`code`, cart, checkout.
- Money is **EUR** only; contact/site URL follow the Home footer canonical values.
- Preserve bilingual French–English tone and Parisian-minimal design tokens (colors, typography, spacing).
- Domain types in `packages/shared/` should model **retail e-commerce** entities (Product, Category, CartLine, Order) aligned with Maison Atelier Rue.
- Evolve types carefully so existing component props are not broken abruptly.
