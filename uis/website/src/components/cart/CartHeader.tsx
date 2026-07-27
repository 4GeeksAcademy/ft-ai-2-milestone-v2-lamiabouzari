import Link from "next/link";

export function CartHeader({
  title = "Shopping Cart",
  subtitle = "Review your items before completing purchase.",
}: {
  title?: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="text-sm text-slate-500">View: Cart</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">{title}</h1>
        <p className="mt-2 text-sm text-slate-600">{subtitle}</p>
      </div>
      <Link
        href="/catalog"
        className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
      >
        Continue shopping
      </Link>
    </div>
  );
}
