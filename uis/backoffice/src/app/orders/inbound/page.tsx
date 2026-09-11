"use client";

import { useEffect, useState } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { StateMessage } from "@/components/ui/StateMessage";
import { ApiError } from "@/lib/api-client";
import { createInboundOrder, listProducts, type Product } from "@/lib/inventory";

export default function InboundOrdersPage() {
  return (
    <RequireAuth>
      <InboundOrdersPageContent />
    </RequireAuth>
  );
}

function InboundOrdersPageContent() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [skuId, setSkuId] = useState<number | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [reference, setReference] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listProducts()
      .then((data) => {
        setProducts(data);
        if (data.length > 0) setSkuId(data[0].id);
      })
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "Unable to load products."))
      .finally(() => setLoadingProducts(false));
  }, []);

  const selectedProduct = products.find((product) => product.id === skuId) ?? null;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setFormSuccess(null);

    if (!selectedProduct) {
      setFormError("Select a product first.");
      return;
    }

    setSubmitting(true);
    try {
      await createInboundOrder({
        sku_id: selectedProduct.id,
        quantity,
        reference,
        warehouse: selectedProduct.warehouse,
      });
      setFormSuccess(`Inbound order for "${selectedProduct.sku}" recorded successfully.`);
      setQuantity(1);
      setReference("");
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Unable to record the inbound order.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="space-y-6">
      <div className="dashboard-card p-6">
        <h2 className="font-display text-2xl text-foreground">Inbound Orders</h2>
        <p className="mt-2 text-sm text-slate-700">
          Record stock arriving into a warehouse for an existing SKU.
        </p>

        {loadingProducts ? (
          <div className="mt-4">
            <StateMessage tone="loading" title="Loading products…" />
          </div>
        ) : loadError ? (
          <div className="mt-4">
            <StateMessage tone="error" title="Could not load products" description={loadError} />
          </div>
        ) : products.length === 0 ? (
          <div className="mt-4">
            <StateMessage tone="empty" title="Create a product before recording inbound orders." />
          </div>
        ) : (
          <form className="mt-4 grid gap-4 sm:grid-cols-2" onSubmit={handleSubmit}>
            <label className="text-sm sm:col-span-2">
              <span className="font-semibold text-slate-700">Product / SKU</span>
              <select
                value={skuId ?? ""}
                onChange={(event) => setSkuId(Number(event.target.value))}
                className="mt-1 w-full rounded-lg border border-line bg-panel px-3 py-2"
              >
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.sku} — {product.name} ({product.warehouse})
                  </option>
                ))}
              </select>
            </label>

            <label className="text-sm">
              <span className="font-semibold text-slate-700">Quantity</span>
              <input
                type="number"
                min={1}
                required
                value={quantity}
                onChange={(event) => setQuantity(Number(event.target.value))}
                className="mt-1 w-full rounded-lg border border-line bg-panel px-3 py-2"
              />
            </label>

            <label className="text-sm">
              <span className="font-semibold text-slate-700">Warehouse</span>
              <input
                readOnly
                value={selectedProduct?.warehouse ?? ""}
                className="mt-1 w-full rounded-lg border border-line bg-panel-soft px-3 py-2 text-slate-600"
              />
            </label>

            <label className="text-sm sm:col-span-2">
              <span className="font-semibold text-slate-700">Reference</span>
              <input
                required
                value={reference}
                onChange={(event) => setReference(event.target.value)}
                placeholder="e.g. PO-2026-001"
                className="mt-1 w-full rounded-lg border border-line bg-panel px-3 py-2"
              />
            </label>

            <div className="sm:col-span-2 space-y-3">
              {formError ? (
                <StateMessage tone="error" title="Could not record inbound order" description={formError} />
              ) : null}
              {formSuccess ? <StateMessage tone="success" title={formSuccess} /> : null}
              <button
                type="submit"
                disabled={submitting}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {submitting ? "Recording…" : "Record inbound order"}
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}
