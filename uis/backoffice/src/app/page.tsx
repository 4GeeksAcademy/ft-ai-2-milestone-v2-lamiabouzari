import {
  PRODUCT_CATEGORIES,
  SITE_CONTACT,
  computeCartTotals,
  formatPrice,
} from "@repo/shared-types";
import { dashboardCartLines } from "@/lib/dashboard";

const orderSnapshot = computeCartTotals(dashboardCartLines);
const unitsInSnapshot = dashboardCartLines.reduce(
  (total, line) => total + line.quantity,
  0
);

export default function HomePage() {
  return (
    <section className="space-y-6">
      <div className="reveal-up rounded-2xl border border-line bg-panel p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent-strong">
          Welcome
        </p>
        <h2 className="mt-2 font-display text-3xl text-foreground sm:text-4xl">
          Bonjour, Maison Atelier Rue team.
        </h2>
        <p className="mt-3 max-w-3xl text-sm text-slate-700 sm:text-base">
          This internal dashboard is powered by shared typed logic from the
          monorepo package and gives a quick operational snapshot for today.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="dashboard-card reveal-up p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-600">
            Subtotal
          </p>
          <p className="metric-value mt-2 text-3xl font-semibold">
            {formatPrice(orderSnapshot.subtotal, orderSnapshot.currency)}
          </p>
        </article>

        <article className="dashboard-card reveal-up reveal-up-delay p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-600">
            Tax ({Math.round(orderSnapshot.taxRate * 100)}%)
          </p>
          <p className="metric-value mt-2 text-3xl font-semibold">
            {formatPrice(orderSnapshot.tax, orderSnapshot.currency)}
          </p>
        </article>

        <article className="dashboard-card reveal-up p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-600">
            Total Value
          </p>
          <p className="metric-value mt-2 text-3xl font-semibold">
            {formatPrice(orderSnapshot.total, orderSnapshot.currency)}
          </p>
        </article>

        <article className="dashboard-card reveal-up reveal-up-delay p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-600">
            Units In Snapshot
          </p>
          <p className="metric-value mt-2 text-3xl font-semibold">
            {unitsInSnapshot}
          </p>
        </article>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <article className="dashboard-card reveal-up p-5 lg:col-span-2">
          <h3 className="font-display text-2xl text-foreground">
            Shared Logic Check
          </h3>
          <p className="mt-2 text-sm text-slate-700">
            Cart totals are computed using <strong>computeCartTotals</strong> and
            amounts are displayed via <strong>formatPrice</strong> from
            packages/shared.
          </p>
          <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
            <div className="rounded-lg bg-panel-soft p-3">
              <dt className="font-semibold text-slate-600">Tracked Categories</dt>
              <dd className="mt-1 text-base text-foreground">
                {PRODUCT_CATEGORIES.length}
              </dd>
            </div>
            <div className="rounded-lg bg-panel-soft p-3">
              <dt className="font-semibold text-slate-600">Support Email</dt>
              <dd className="mt-1 text-base text-foreground">{SITE_CONTACT.email}</dd>
            </div>
          </dl>
        </article>

        <article className="dashboard-card reveal-up p-5">
          <h3 className="font-display text-xl text-foreground">Brand Contact</h3>
          <p className="mt-3 text-sm text-slate-700">{SITE_CONTACT.brandName}</p>
          <p className="text-sm text-slate-700">{SITE_CONTACT.phone}</p>
          <p className="text-sm text-slate-700">{SITE_CONTACT.address}</p>
        </article>
      </div>
    </section>
  );
}
