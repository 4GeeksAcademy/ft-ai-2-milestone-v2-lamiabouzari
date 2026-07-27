import type { Product } from "@repo/shared-types";
import { ProductCard } from "./ProductCard";

type RelatedProductsProps = {
  products: Product[];
  title?: string;
  subtitle?: string;
};

export function RelatedProducts({
  products,
  title = "From the catalog",
  subtitle = "Product list aligned with the catalog grid style",
}: RelatedProductsProps) {
  return (
    <section className="mt-10 border-t border-slate-200 pt-8">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <h2 className="text-2xl font-semibold tracking-tight text-slate-900">
          {title}
        </h2>
        <p className="text-sm text-slate-500">{subtitle}</p>
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {products.map((product) => (
          <ProductCard key={product.id} product={product} variant="compact" />
        ))}
      </div>
    </section>
  );
}
