interface StockLevelBadgeProps {
  readonly currentStock: number;
}

type StockLevel = "out" | "low" | "in";

/** Visual stock-level indicator: out of stock / low stock / in stock. */
export function StockLevelBadge({ currentStock }: StockLevelBadgeProps) {
  const level: StockLevel =
    currentStock <= 0 ? "out" : currentStock <= 5 ? "low" : "in";

  const styles: Record<StockLevel, string> = {
    out: "bg-red-100 text-red-700",
    low: "bg-amber-100 text-amber-700",
    in: "bg-emerald-100 text-emerald-700",
  };

  const labels: Record<StockLevel, string> = {
    out: "Out of stock",
    low: "Low stock",
    in: "In stock",
  };

  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${styles[level]}`}>
      {labels[level]}
    </span>
  );
}
