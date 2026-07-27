# Maison Atelier Rue

French business-casual retailer with understated essentials, designed in Paris for calm, confident movement. The brand pairs quiet tailoring with breathable textures and easy silhouettes — shirts, blazers, trousers, footwear, and accessories sold through a Parisian-minimal e-commerce experience.

**Contact:** bonjour@maisonatelierrue.example · +33 1 00 45 67 89 · 14 Rue de la Tranquillité, Paris  
**Reference site:** `uis/website_v1/`

## Why this company

- Matches the existing static prototype (`website_v1`) — brand, catalog, and copy already define the product.
- Clear e-commerce domain: products, categories, sizes, cart, and checkout.
- Strong visual identity (Parisian-minimal tokens) that the Next.js migration must preserve.

## Challenges Maison Atelier Rue might have

- **Catalog & product data** — consistent SKUs, sizes, pricing (EUR), and bilingual (French–English) copy across Home, Catalog, and Product views.
- **Inventory & sizing** — stock by size across footwear, shirts, pants, and accessories without a real backend yet.
- **Cart & checkout** — multi-step payment flow with accurate subtotals, tax, and totals from mock or future APIs.
- **Migration fidelity** — moving from static HTML to Next.js without losing SEO, shared chrome (navbar/footer), or design tokens.
- **Future ops** — order fulfillment, returns, and customer support once a backend exists — domain language should stay product/order-centric (not logistics-carrier).
