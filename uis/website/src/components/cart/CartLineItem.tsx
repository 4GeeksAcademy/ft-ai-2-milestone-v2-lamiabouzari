"use client";

import { formatPrice, type CartLine } from "@repo/shared-types";

type CartLineItemProps = {
  line: CartLine;
  onQuantityChange?: (lineId: string, quantity: number) => void;
};

export function CartLineItem({ line, onQuantityChange }: CartLineItemProps) {
  const lineTotal = line.unitPrice * line.quantity;

  return (
    <li className="grid gap-4 px-4 py-5 sm:grid-cols-[minmax(0,1.3fr)_0.7fr_0.7fr_0.7fr] sm:items-center sm:px-5">
      <div className="flex min-w-0 gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          className="h-16 w-16 rounded-md border border-slate-200 object-cover"
          src={line.image}
          alt={line.imageAlt ?? line.name}
        />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">
            {line.name}
          </p>
          <p className="mt-0.5 text-xs text-slate-500">{line.code}</p>
        </div>
      </div>
      <p className="text-sm text-slate-700 sm:text-right">
        <span className="text-slate-500 sm:hidden">Unit price: </span>
        {formatPrice(line.unitPrice, line.currency)}
      </p>
      <label className="flex items-center gap-2 text-sm sm:justify-end">
        <span className="text-slate-500 sm:hidden">Quantity:</span>
        <input
          type="number"
          min={1}
          value={line.quantity}
          onChange={(event) =>
            onQuantityChange?.(
              line.id,
              Math.max(1, Number(event.target.value) || 1)
            )
          }
          className="w-20 rounded-md border border-slate-300 px-2 py-1.5 text-right text-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
        />
      </label>
      <p className="text-sm font-semibold text-slate-900 sm:text-right">
        <span className="text-slate-500 sm:hidden">Total: </span>
        {formatPrice(lineTotal, line.currency)}
      </p>
    </li>
  );
}
