"use client";

import { useState } from "react";

type ProductDetailTabsProps = {
  details: string[];
  materials: string[];
};

export function ProductDetailTabs({
  details,
  materials,
}: ProductDetailTabsProps) {
  const [active, setActive] = useState<"details" | "materials">("details");

  return (
    <section className="mt-8 min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="grid grid-cols-2 gap-2 rounded-lg bg-white p-1">
        <button
          type="button"
          onClick={() => setActive("details")}
          className={`rounded-md px-3 py-2 text-sm font-semibold underline transition-colors ${
            active === "details"
              ? "bg-navbase text-navtext"
              : "text-slate-900 hover:bg-slate-500 hover:text-white"
          }`}
        >
          Product details
        </button>
        <button
          type="button"
          onClick={() => setActive("materials")}
          className={`rounded-md px-3 py-2 text-sm font-semibold underline transition-colors ${
            active === "materials"
              ? "bg-navbase text-navtext"
              : "text-slate-900 hover:bg-slate-500 hover:text-white"
          }`}
        >
          Materials
        </button>
      </div>

      <div className="mt-4 px-1 text-sm text-slate-700">
        <ul className="list-none space-y-2 pl-2">
          {(active === "details" ? details : materials).map((item) => (
            <li key={item} className="before:mr-2 before:content-['-']">
              {item}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
