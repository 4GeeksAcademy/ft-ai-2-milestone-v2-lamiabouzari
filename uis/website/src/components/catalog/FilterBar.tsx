"use client";

import {
  CATALOG_SIZE_FILTERS,
  FOOTER_CATEGORIES,
  type ProductCategory,
} from "@repo/shared-types";

export type FilterBarValues = {
  category: "all" | ProductCategory;
  size: string;
};

type FilterBarProps = {
  value: FilterBarValues;
  onChange: (next: FilterBarValues) => void;
};

export function FilterBar({ value, onChange }: FilterBarProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 sm:p-5">
      <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-600">
        Filter Bar
      </h2>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">
            Filter by category
          </span>
          <select
            value={value.category}
            onChange={(event) =>
              onChange({
                ...value,
                category: event.target.value as FilterBarValues["category"],
              })
            }
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-800 focus:border-sleeve focus:outline-none focus:ring-2 focus:ring-sleeve/40"
          >
            <option value="all">All categories</option>
            {FOOTER_CATEGORIES.map(({ category, label }) => (
              <option key={category} value={category}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">
            Filter by size
          </span>
          <select
            value={value.size}
            onChange={(event) =>
              onChange({ ...value, size: event.target.value })
            }
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-800 focus:border-sleeve focus:outline-none focus:ring-2 focus:ring-sleeve/40"
          >
            <option value="all">All sizes</option>
            {CATALOG_SIZE_FILTERS.map((size) => (
              <option key={size} value={size}>
                {size === "one-size" ? "One Size" : size.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}
