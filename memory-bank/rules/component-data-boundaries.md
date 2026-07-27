# Component & Data Boundaries

- Extract distinct UI elements into **reusable components** (navbar, footer, product card, cart line item, checkout steps).
- Use a **placeholder product data model** in `packages/shared/types/` — no real API calls or database wiring yet.
- Keep cart/checkout state client-side or in mock data until a backend milestone explicitly adds persistence.
- Do not introduce a second product schema inside the Next.js app; import from `@repo/shared-types`.
