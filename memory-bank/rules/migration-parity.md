# Migration Parity (Non-Negotiable)

The Next.js app must eventually match `uis/website_v1/SPEC.md`. Follow the phased process in `memory-bank/specs/migration-process.md`, including the **data + component review gate** before migrating views.

- **Views:** Home, Catalog, Product, Cart, Checkout (3-step payment flow)
- **Shared chrome:** Navbar and footer reused on every view
- **SEO:** Semantic HTML, meta descriptions, structured data where the reference has it
- **Responsive:** Mobile, tablet, and desktop — verify at ~375px, ~768px, and ~1280px
- **Visual fidelity:** Preserve design tokens (colors, typography, spacing) from `website_v1`; do not redesign unless asked

When a change would drop a spec requirement, stop and flag it instead of shipping a partial migration.
