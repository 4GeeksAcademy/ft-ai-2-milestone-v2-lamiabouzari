import Link from "next/link";
import type { Product } from "@repo/shared-types";
import { ProductCard } from "./ProductCard";

type ProductRailProps = {
  title: string;
  products: Product[];
  viewAllHref?: string;
  labelledById: string;
};

export function ProductRail({
  title,
  products,
  viewAllHref = "/catalog",
  labelledById,
}: ProductRailProps) {
  return (
    <section aria-labelledby={labelledById}>
      <div className="mb-5 flex items-end justify-between gap-4">
        <h2 id={labelledById} className="text-2xl text-slate-900 sm:text-3xl">
          {title}
        </h2>
        <Link
          href={viewAllHref}
          className="text-sm font-semibold text-slate-700 hover:text-slate-900"
        >
          View all
        </Link>
      </div>
      <ul
        className="horizontal-rail flex snap-x gap-4 overflow-x-auto pb-2"
        aria-label={`${title} products`}
      >
        {products.map((product) => (
          <li key={product.id} className="w-64 shrink-0 snap-start sm:w-72">
            <ProductCard product={product} variant="rail" />
          </li>
        ))}
      </ul>
    </section>
  );
}
