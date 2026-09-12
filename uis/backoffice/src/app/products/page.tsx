"use client";

import { useEffect, useMemo, useState } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { StateMessage } from "@/components/ui/StateMessage";
import { StockLevelBadge } from "@/components/ui/StockLevelBadge";
import { ApiError } from "@/lib/api-client";
import {
  CATEGORIES,
  WAREHOUSES,
  createProduct,
  listProducts,
  type Category,
  type Product,
  type Warehouse,
} from "@/lib/inventory";
import { telemetryService } from "@/services/telemetry";

export default function ProductsPage() {
  return (
    <RequireAuth>
      <ProductsPageContent />
    </RequireAuth>
  );
}

function ProductsPageContent() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [warehouseFilter, setWarehouseFilter] = useState<Warehouse | "all">("all");
  const [categoryFilter, setCategoryFilter] = useState<Category | "all">("all");

  const [form, setForm] = useState({
    name: "",
    sku: "",
    client_name: "",
    category: "fashion" as Category,
    warehouse: "LA" as Warehouse,
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function loadProducts() {
    setLoadError(null);
    try {
      const data = await listProducts();
      setProducts(data);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Unable to load products.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    listProducts()
      .then(setProducts)
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "Unable to load products."))
      .finally(() => setLoading(false));
  }, []);

  const filteredProducts = useMemo(() => {
    return products.filter((product) => {
      if (warehouseFilter !== "all" && product.warehouse !== warehouseFilter) return false;
      if (categoryFilter !== "all" && product.category !== categoryFilter) return false;
      return true;
    });
  }, [products, warehouseFilter, categoryFilter]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setFormSuccess(null);
    setSubmitting(true);
    try {
      await createProduct(form);
      telemetryService.track("product_created", {
        sku: form.sku,
        category: form.category,
        warehouse: form.warehouse,
      });
      setFormSuccess(`SKU "${form.sku}" created successfully.`);
      setForm({ name: "", sku: "", client_name: "", category: "fashion", warehouse: "LA" });
      await loadProducts();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Unable to create the product.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="space-y-6">
      <div className="dashboard-card p-6">
        <h2 className="font-display text-2xl text-foreground">Products</h2>
        <p className="mt-2 text-sm text-slate-700">
          Browse SKUs and their current stock across warehouses.
        </p>

        <div className="mt-4 flex flex-wrap gap-3">
          <label className="text-sm">
            <span className="mr-2 font-semibold text-slate-700">Warehouse</span>
            <select
              value={warehouseFilter}
              onChange={(event) => setWarehouseFilter(event.target.value as Warehouse | "all")}
              className="rounded-lg border border-line bg-panel px-2 py-1"
            >
              <option value="all">All</option>
              {WAREHOUSES.map((warehouse) => (
                <option key={warehouse} value={warehouse}>
                  {warehouse}
                </option>
              ))}
            </select>
          </label>

          <label className="text-sm">
            <span className="mr-2 font-semibold text-slate-700">Category</span>
            <select
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value as Category | "all")}
              className="rounded-lg border border-line bg-panel px-2 py-1"
            >
              <option value="all">All</option>
              {CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-4">
          {loading ? (
            <StateMessage tone="loading" title="Loading products…" />
          ) : loadError ? (
            <StateMessage tone="error" title="Could not load products" description={loadError} />
          ) : filteredProducts.length === 0 ? (
            <StateMessage tone="empty" title="No products match the current filters." />
          ) : (
            <div className="overflow-x-auto">
              <table className="mt-2 w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase tracking-wide text-slate-600">
                    <th className="py-2 pr-4">SKU</th>
                    <th className="py-2 pr-4">Name</th>
                    <th className="py-2 pr-4">Client</th>
                    <th className="py-2 pr-4">Category</th>
                    <th className="py-2 pr-4">Warehouse</th>
                    <th className="py-2 pr-4">Current Stock</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProducts.map((product) => (
                    <tr key={product.id} className="border-b border-line/60">
                      <td className="py-2 pr-4 font-semibold text-foreground">{product.sku}</td>
                      <td className="py-2 pr-4">{product.name}</td>
                      <td className="py-2 pr-4">{product.client_name}</td>
                      <td className="py-2 pr-4">{product.category}</td>
                      <td className="py-2 pr-4">{product.warehouse}</td>
                      <td className="py-2 pr-4">
                        <span className="font-semibold">{product.current_stock}</span>{" "}
                        <StockLevelBadge currentStock={product.current_stock} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="dashboard-card p-6">
        <h3 className="font-display text-xl text-foreground">Create Product</h3>
        <form className="mt-4 grid gap-4 sm:grid-cols-2" onSubmit={handleSubmit}>
          <label className="text-sm">
            <span className="font-semibold text-slate-700">Name</span>
            <input
              required
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              className="mt-1 w-full rounded-lg border border-line bg-panel px-3 py-2"
            />
          </label>

          <label className="text-sm">
            <span className="font-semibold text-slate-700">SKU code</span>
            <input
              required
              value={form.sku}
              onChange={(event) => setForm({ ...form, sku: event.target.value })}
              className="mt-1 w-full rounded-lg border border-line bg-panel px-3 py-2"
            />
          </label>

          <label className="text-sm">
            <span className="font-semibold text-slate-700">Client name</span>
            <input
              required
              value={form.client_name}
              onChange={(event) => setForm({ ...form, client_name: event.target.value })}
              className="mt-1 w-full rounded-lg border border-line bg-panel px-3 py-2"
            />
          </label>

          <label className="text-sm">
            <span className="font-semibold text-slate-700">Category</span>
            <select
              value={form.category}
              onChange={(event) => setForm({ ...form, category: event.target.value as Category })}
              className="mt-1 w-full rounded-lg border border-line bg-panel px-3 py-2"
            >
              {CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>

          <label className="text-sm">
            <span className="font-semibold text-slate-700">Warehouse</span>
            <select
              value={form.warehouse}
              onChange={(event) => setForm({ ...form, warehouse: event.target.value as Warehouse })}
              className="mt-1 w-full rounded-lg border border-line bg-panel px-3 py-2"
            >
              {WAREHOUSES.map((warehouse) => (
                <option key={warehouse} value={warehouse}>
                  {warehouse}
                </option>
              ))}
            </select>
          </label>

          <div className="sm:col-span-2 space-y-3">
            {formError ? (
              <StateMessage tone="error" title="Could not create product" description={formError} />
            ) : null}
            {formSuccess ? <StateMessage tone="success" title={formSuccess} /> : null}
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            >
              {submitting ? "Creating…" : "Create product"}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
