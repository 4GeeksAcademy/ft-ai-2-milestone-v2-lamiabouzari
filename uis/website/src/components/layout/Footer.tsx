import Link from "next/link";
import { FOOTER_CATEGORIES, SITE_CONTACT } from "@repo/shared-types";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-clay/70 bg-white/80" role="contentinfo">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:grid-cols-2 sm:px-8 lg:grid-cols-4 lg:px-10">
        <section aria-labelledby="footer-brand-title" className="sm:col-span-2 lg:col-span-1">
          <h2 id="footer-brand-title" className="text-lg text-slate-900">
            {SITE_CONTACT.brandName}
          </h2>
          <p className="mt-3 max-w-xs text-sm leading-relaxed text-slate-600">
            Business-casual essentials designed in Paris for calm, confident
            movement.
          </p>
        </section>

        <nav aria-labelledby="footer-categories-title">
          <h2
            id="footer-categories-title"
            className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500"
          >
            Categories
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            {FOOTER_CATEGORIES.map(({ category, label }) => (
              <li key={category}>
                <Link
                  href={`/catalog?category=${category}`}
                  className="footer-link"
                >
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <nav aria-labelledby="footer-legal-title">
          <h2
            id="footer-legal-title"
            className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500"
          >
            Legal
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            <li>
              <a href="#" className="footer-link">
                Terms and conditions
              </a>
            </li>
            <li>
              <a href="#" className="footer-link">
                Privacy policy
              </a>
            </li>
            <li>
              <a href="#" className="footer-link">
                About the brand
              </a>
            </li>
          </ul>
        </nav>

        <section aria-labelledby="footer-contact-title">
          <h2
            id="footer-contact-title"
            className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500"
          >
            Contact
          </h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            <li>
              <a href={`mailto:${SITE_CONTACT.email}`} className="footer-link">
                {SITE_CONTACT.email}
              </a>
            </li>
            <li>
              <a
                href={`tel:${SITE_CONTACT.phone.replace(/\s/g, "")}`}
                className="footer-link"
              >
                {SITE_CONTACT.phone}
              </a>
            </li>
            <li>{SITE_CONTACT.address}</li>
          </ul>
        </section>
      </div>
    </footer>
  );
}
