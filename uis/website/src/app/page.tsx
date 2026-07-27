import type { Metadata } from "next";
import { SITE_CONTACT } from "@repo/shared-types";
import { EditorialDivider } from "@/components/home/EditorialDivider";
import { Hero } from "@/components/home/Hero";
import { ProductRail } from "@/components/product/ProductRail";
import { bestSellers, newArrivals } from "@/data/catalog";

export const metadata: Metadata = {
  title: "Home",
  description:
    "Maison Atelier Rue is a French business-casual house. Discover new arrivals and best sellers in an airy Parisian-minimal setting.",
  openGraph: {
    title: "Home | Maison Atelier Rue",
    description:
      "Maison Atelier Rue is a French business-casual house. Discover new arrivals and best sellers in an airy Parisian-minimal setting.",
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: SITE_CONTACT.brandName,
      url: SITE_CONTACT.url,
      logo: `${SITE_CONTACT.url}/assets/logo-wordmark.png`,
      description: "French business-casual retailer with understated essentials.",
      contactPoint: {
        "@type": "ContactPoint",
        contactType: "customer support",
        email: SITE_CONTACT.email,
      },
    },
    {
      "@type": "WebSite",
      name: SITE_CONTACT.brandName,
      url: SITE_CONTACT.url,
      potentialAction: {
        "@type": "SearchAction",
        target: `${SITE_CONTACT.url}/catalog?q={search_term_string}`,
        "query-input": "required name=search_term_string",
      },
    },
    {
      "@type": "ItemList",
      name: "New arrivals",
      itemListElement: newArrivals.map((product, index) => ({
        "@type": "Product",
        position: index + 1,
        name: product.name,
      })),
    },
  ],
};

export default function HomePage() {
  return (
    <main
      id="main-content"
      className="mx-auto max-w-6xl px-4 pb-20 pt-6 sm:px-8 lg:px-10"
    >
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <Hero
        title="Quiet tailoring for bright city mornings."
        body="Maison Atelier Rue pairs French business-casual silhouettes with breathable textures, gentle structure, and easy movement."
      />

      <EditorialDivider className="mt-12" />

      <div className="mt-10 space-y-14">
        <ProductRail
          title="New arrivals"
          products={newArrivals}
          labelledById="new-arrivals-title"
        />
        <ProductRail
          title="Best sellers"
          products={bestSellers}
          labelledById="best-sellers-title"
        />
      </div>
    </main>
  );
}
