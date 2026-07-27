import type { Metadata } from "next";
import {
  FOOTER_CATEGORIES,
  type ProductCategory,
} from "@repo/shared-types";
import { CatalogDemo } from "@/components/catalog/CatalogDemo";
import { CatalogIntro } from "@/components/catalog/CatalogIntro";
import type { FilterBarValues } from "@/components/catalog/FilterBar";
import { catalogProducts } from "@/data/catalog";

export const metadata: Metadata = {
  title: "Catalogue",
  description:
    "Browse Maison Atelier Rue products. Filter Parisian business-casual pieces by category and size.",
};

type CatalogPageProps = {
  searchParams: Promise<{ category?: string; size?: string; q?: string }>;
};

function parseFilters(params: {
  category?: string;
  size?: string;
}): FilterBarValues {
  const categoryValues = FOOTER_CATEGORIES.map((item) => item.category);
  const category =
    params.category &&
    categoryValues.includes(params.category as ProductCategory)
      ? (params.category as ProductCategory)
      : "all";
  const size = params.size && params.size.length > 0 ? params.size : "all";
  return { category, size };
}

export default async function CatalogPage({ searchParams }: CatalogPageProps) {
  const params = await searchParams;
  const initialFilters = parseFilters(params);

  const query = params.q?.trim().toLowerCase();
  const products = query
    ? catalogProducts.filter(
        (product) =>
          product.name.toLowerCase().includes(query) ||
          product.shortDescription.toLowerCase().includes(query) ||
          product.categoryLabel.toLowerCase().includes(query)
      )
    : catalogProducts;

  return (
    <main
      id="main-content"
      className="mx-auto w-full max-w-6xl flex-1 px-4 pb-16 pt-10 sm:px-8"
    >
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <CatalogIntro />
        {query ? (
          <p className="mt-4 text-sm text-slate-600">
            Showing results for &ldquo;{params.q}&rdquo;
          </p>
        ) : null}
        <div className="mt-8">
          <CatalogDemo products={products} initialFilters={initialFilters} />
        </div>
      </section>
    </main>
  );
}
