import type { Metadata } from "next";
import { CartDemo } from "@/components/cart/CartDemo";
import { sampleCartLines } from "@/data/catalog";

export const metadata: Metadata = {
  title: "Cart",
  description: "Review your Maison Atelier Rue bag before checkout.",
};

export default function CartPage() {
  return (
    <main
      id="main-content"
      className="mx-auto max-w-6xl px-4 pb-16 pt-10 sm:px-8"
    >
      <CartDemo initialLines={sampleCartLines} />
    </main>
  );
}
