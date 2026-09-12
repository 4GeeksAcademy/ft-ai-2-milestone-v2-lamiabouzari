"use client";

import { useEffect, useState } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { StateMessage } from "@/components/ui/StateMessage";
import { ApiError } from "@/lib/api-client";
import {
  EXIT_TYPES,
  createOutboundOrder,
  listProducts,
  type ExitType,
  type Product,
} from "@/lib/inventory";

export default function OutboundOrdersPage() {
  return (
    <RequireAuth>
      <OutboundOrdersPageContent />
    </RequireAuth>
  );
}

function OutboundOrdersPageContent() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [skuId, setSkuId] = useState<number | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [exitType, setExitType] = useState<ExitType>("dispatch");
  const [trackingNumber, setTrackingNumber] = useState("");
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
  const requiresTrackingNumber = exitType === "dispatch";
  const exceedsStock = selectedProduct != null && quantity > selectedProduct.current_stock;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setFormSuccess(null);

    if (!selectedProduct) {
      setFormError("Select a product first.");
      return;
    }

    if (exceedsStock) {
      setFormError("Quantity exceeds available stock for this SKU.");
      return;
    }

    setSubmitting(true);
    try {
      await createOutboundOrder({
        sku_id: selectedProduct.id,
        quantity,
        exit_type: exitType,
        tracking_number: requiresTrackingNumber ? trackingNumber : null,
        warehouse: selectedProduct.warehouse,
      });
      setFormSuccess(`Outbound order for "${selectedProduct.sku}" recorded successfully.`);
      setQuantity(1);
      setTrackingNumber("");
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Unable to record the outbound order.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="space-y-6">
      <div className="dashboard-card p-6">
        <h2 className="font-display text-2xl text-foreground">Outbound Orders</h2>
        <p className="mt-2 text-sm text-slate-700">
          Record stock leaving a warehouse — either dispatched to a client or written off as a loss.
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
            <StateMessage tone="empty" title="Create a product before recording outbound orders." />
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
                    {product.sku} — {product.name} ({product.warehouse}, stock: {product.current_stock})
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs font-semibold text-slate-600">
                Available stock: {selectedProduct?.current_stock ?? "—"}
              </p>
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

            <label className="text-sm">
              <span className="font-semibold text-slate-700">Exit type</span>
              <select
                value={exitType}
                onChange={(event) => setExitType(event.target.value as ExitType)}
                className="mt-1 w-full rounded-lg border border-line bg-panel px-3 py-2"
              >
                {EXIT_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </label>

            {requiresTrackingNumber ? (
              <label className="text-sm">
                <span className="font-semibold text-slate-700">Tracking number</span>
                <input
                  required
                  value={trackingNumber}
                  onChange={(event) => setTrackingNumber(event.target.value)}
                  placeholder="Required for dispatch"
                  className="mt-1 w-full rounded-lg border border-line bg-panel px-3 py-2"
                />
              </label>
            ) : null}

            <div className="sm:col-span-2 space-y-3">
              {exceedsStock ? (
                <StateMessage
                  tone="error"
                  title="Quantity exceeds available stock"
                  description={`Only ${selectedProduct?.current_stock} unit(s) available for this SKU.`}
                />
              ) : null}
              {formError ? (
                <StateMessage tone="error" title="Could not record outbound order" description={formError} />
              ) : null}
              {formSuccess ? <StateMessage tone="success" title={formSuccess} /> : null}
              <button
                type="submit"
                disabled={submitting || exceedsStock}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {submitting ? "Recording…" : "Record outbound order"}
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}
