"use client";

import { useMemo, useState } from "react";
import type { Product } from "@repo/shared-types";
import { EmptyFilterState } from "@/components/catalog/EmptyFilterState";
import {
  FilterBar,
  type FilterBarValues,
} from "@/components/catalog/FilterBar";
import { ProductGrid } from "@/components/catalog/ProductGrid";

type CatalogDemoProps = {
  products: Product[];
  initialFilters?: FilterBarValues;
};

export function CatalogDemo({
  products,
  initialFilters = { category: "all", size: "all" },
}: CatalogDemoProps) {
  const [filters, setFilters] = useState<FilterBarValues>(initialFilters);
  const filtered = useMemo(() => {
    return products.filter((product) => {
      const categoryOk =
        filters.category === "all" || product.category === filters.category;
      const sizeOk =
        filters.size === "all" || product.sizes.includes(filters.size);
      return categoryOk && sizeOk;
    });
  }, [filters, products]);

  return (
    <div>
      <FilterBar value={filters} onChange={setFilters} />
      {filtered.length > 0 ? (
        <ProductGrid products={filtered} />
      ) : (
        <EmptyFilterState />
      )}
    </div>
  );
}
