import { formatPrice, type CartLine, type CartTotals } from "@repo/shared-types";

type CheckoutOrderSummaryProps = {
  lines: CartLine[];
  totals: CartTotals;
};

export function CheckoutOrderSummary({
  lines,
  totals,
}: CheckoutOrderSummaryProps) {
  return (
    <section className="rounded-2xl border border-stone/90 bg-white/85 p-5 shadow-sm">
      <h3 className="font-serif text-2xl">Order Summary</h3>
      <ul className="mt-4 space-y-4 text-sm text-ink/80">
        {lines.map((line) => (
          <li
            key={line.id}
            className="flex items-center justify-between border-b border-stone/80 pb-3"
          >
            <span>{line.name}</span>
            <span>{formatPrice(line.unitPrice * line.quantity, line.currency)}</span>
          </li>
        ))}
        <li className="mt-2 flex items-center justify-between border-t border-stone/80 pt-3 text-xs uppercase tracking-[0.12em] text-ink/70">
          <span>Order Total</span>
          <span>{formatPrice(totals.total, totals.currency)}</span>
        </li>
      </ul>
    </section>
  );
}
