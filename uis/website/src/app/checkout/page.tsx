import type { Metadata } from "next";
import Link from "next/link";
import { computeCartTotals, formatPrice } from "@repo/shared-types";
import { AnnouncementBar } from "@/components/checkout/AnnouncementBar";
import { CheckoutIntro } from "@/components/checkout/CheckoutIntro";
import { CheckoutOrderSummary } from "@/components/checkout/CheckoutOrderSummary";
import { CheckoutSteps } from "@/components/checkout/CheckoutSteps";
import { ProductCard } from "@/components/product/ProductCard";
import { bestSellers, sampleCartLines } from "@/data/catalog";

export const metadata: Metadata = {
  title: "Checkout",
  description:
    "Complete your Maison Atelier Rue order: personal details, shipping address, and secure card payment in three elegant steps.",
};

const cartTotals = computeCartTotals(sampleCartLines);
const recommended = bestSellers.slice(0, 4);

export default function CheckoutPage() {
  return (
    <>
      <AnnouncementBar />
      <main
        id="main-content"
        className="mx-auto max-w-6xl px-4 pb-16 sm:px-8"
      >
        <div className="pt-6">
          <CheckoutIntro />
        </div>

        <section className="mt-8 grid gap-7 lg:grid-cols-[1.35fr_0.65fr]">
          <CheckoutSteps
            orderTotalLabel={`Order Total: ${formatPrice(cartTotals.total)} (Tax Included)`}
          />
          <aside className="space-y-5">
            <CheckoutOrderSummary lines={sampleCartLines} totals={cartTotals} />
          </aside>
        </section>

        <section className="mt-8 rounded-2xl border border-stone/90 bg-white/85 p-5 shadow-sm md:p-7">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-ink/55">
                Recommended for You
              </p>
              <h2 className="mt-1 font-serif text-3xl">Complete Your Look</h2>
            </div>
            <Link
              className="text-sm font-medium text-ink/70 transition hover:text-ink"
              href="/catalog"
            >
              Browse All Products
            </Link>
          </div>
          <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {recommended.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                variant="compact"
              />
            ))}
          </div>
        </section>
      </main>
    </>
  );
}
