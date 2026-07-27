import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { SITE_CONTACT, formatPrice } from "@repo/shared-types";
import { ProductDetailTabs } from "@/components/product/ProductDetailTabs";
import { ProductGallery } from "@/components/product/ProductGallery";
import { ProductInfo } from "@/components/product/ProductInfo";
import { RelatedProducts } from "@/components/product/RelatedProducts";
import { StylingSuggestions } from "@/components/product/StylingSuggestions";
import {
  catalogProducts,
  getProductBySlug,
  products,
} from "@/data/catalog";

type ProductPageProps = {
  params: Promise<{ slug: string }>;
};

export async function generateStaticParams() {
  return products.map((product) => ({ slug: product.slug }));
}

export async function generateMetadata({
  params,
}: ProductPageProps): Promise<Metadata> {
  const { slug } = await params;
  const product = getProductBySlug(slug);
  if (!product) {
    return { title: "Product" };
  }
  return {
    title: product.name,
    description: product.shortDescription,
    openGraph: {
      title: `${product.name} | ${SITE_CONTACT.brandName}`,
      description: product.shortDescription,
      ...(product.image ? { images: [{ url: product.image }] } : {}),
    },
  };
}

export default async function ProductPage({ params }: ProductPageProps) {
  const { slug } = await params;
  const product = getProductBySlug(slug);
  if (!product) notFound();

  const related = catalogProducts
    .filter((item) => item.id !== product.id)
    .slice(0, 4);

  const productJsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.shortDescription,
    sku: product.code,
    image: product.image ? [product.image] : undefined,
    brand: {
      "@type": "Brand",
      name: SITE_CONTACT.brandName,
    },
    offers: {
      "@type": "Offer",
      priceCurrency: product.currency,
      price: product.price.toFixed(2),
      availability: "https://schema.org/InStock",
      url: `${SITE_CONTACT.url}/product/${product.slug}`,
    },
  };

  return (
    <main
      id="main-content"
      className="mx-auto max-w-6xl px-4 pb-16 pt-10 sm:px-8"
    >
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(productJsonLd) }}
      />

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <p className="text-sm uppercase tracking-[0.2em] text-slate-500">
          French business casual
        </p>

        <div className="mt-5 grid gap-10 lg:grid-cols-2">
          <ProductGallery product={product} />
          <div className="flex min-w-0 flex-col">
            <ProductInfo product={product} />
            {product.details && product.materials ? (
              <ProductDetailTabs
                details={product.details}
                materials={product.materials}
              />
            ) : (
              <section className="mt-8 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                {formatPrice(product.price, product.currency)} · Code{" "}
                {product.code}
              </section>
            )}
          </div>
        </div>

        {product.stylingSuggestions ? (
          <StylingSuggestions text={product.stylingSuggestions} />
        ) : null}

        <RelatedProducts products={related} />
      </section>
    </main>
  );
}
