import Link from "next/link";
import { formatPrice, type CartTotals } from "@repo/shared-types";

type CartSummaryProps = {
  totals: CartTotals;
};

export function CartSummary({ totals }: CartSummaryProps) {
  const taxPercent = Math.round(totals.taxRate * 100);

  return (
    <aside
      aria-label="Order summary"
      className="h-fit rounded-xl border border-slate-200 bg-slate-50 p-5 lg:sticky lg:top-6"
    >
      <h2 className="text-lg font-semibold text-slate-900">Order Summary</h2>
      <dl className="mt-4 space-y-3 text-sm">
        <div className="flex items-center justify-between">
          <dt className="text-slate-600">Subtotal</dt>
          <dd className="font-medium text-slate-900">
            {formatPrice(totals.subtotal, totals.currency)}
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-slate-600">Tax ({taxPercent}%)</dt>
          <dd className="font-medium text-slate-900">
            {formatPrice(totals.tax, totals.currency)}
          </dd>
        </div>
        <div className="border-t border-slate-200 pt-3" />
        <div className="flex items-center justify-between">
          <dt className="text-base font-semibold text-slate-900">Total</dt>
          <dd className="text-base font-semibold text-slate-900">
            {formatPrice(totals.total, totals.currency)}
          </dd>
        </div>
      </dl>

      <Link
        href="/checkout"
        className="mt-6 block w-full rounded-lg bg-navbase px-4 py-3 text-center text-sm font-semibold text-white transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-sleeve focus:ring-offset-2"
      >
        Purchase
      </Link>
    </aside>
  );
}
