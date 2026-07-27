"use client";

import { useMemo, useState } from "react";
import { computeCartTotals, type CartLine } from "@repo/shared-types";
import { CartHeader } from "@/components/cart/CartHeader";
import { CartLineItem } from "@/components/cart/CartLineItem";
import { CartSummary } from "@/components/cart/CartSummary";

type CartDemoProps = {
  initialLines: CartLine[];
};

export function CartDemo({ initialLines }: CartDemoProps) {
  const [lines, setLines] = useState(initialLines);
  const totals = useMemo(() => computeCartTotals(lines), [lines]);

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
      <CartHeader />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section
          aria-label="Cart items"
          className="overflow-hidden rounded-xl border border-slate-200"
        >
          <div className="hidden grid-cols-[minmax(0,1.3fr)_0.7fr_0.7fr_0.7fr] gap-3 border-b border-slate-200 bg-slate-50 px-5 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500 sm:grid">
            <p>Product</p>
            <p>Unit price</p>
            <p>Quantity</p>
            <p>Total</p>
          </div>
          <ul className="divide-y divide-slate-200" aria-live="polite">
            {lines.map((line) => (
              <CartLineItem
                key={line.id}
                line={line}
                onQuantityChange={(lineId, quantity) =>
                  setLines((current) =>
                    current.map((item) =>
                      item.id === lineId ? { ...item, quantity } : item
                    )
                  )
                }
              />
            ))}
          </ul>
        </section>
        <CartSummary totals={totals} />
      </div>
    </section>
  );
}
