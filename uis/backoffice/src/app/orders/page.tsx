"use client";

import { useEffect, useMemo, useState } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { StateMessage } from "@/components/ui/StateMessage";
import { ApiError } from "@/lib/api-client";
import { listOrders, type Order } from "@/lib/inventory";

export default function OrderHistoryPage() {
  return (
    <RequireAuth>
      <OrderHistoryPageContent />
    </RequireAuth>
  );
}

function OrderHistoryPageContent() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [movementFilter, setMovementFilter] = useState<"all" | "inbound" | "outbound">("all");

  useEffect(() => {
    listOrders()
      .then(setOrders)
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "Unable to load orders."))
      .finally(() => setLoading(false));
  }, []);

  const filteredOrders = useMemo(() => {
    if (movementFilter === "all") return orders;
    return orders.filter((order) => order.movement_type === movementFilter);
  }, [orders, movementFilter]);

  return (
    <section className="space-y-6">
      <div className="dashboard-card p-6">
        <h2 className="font-display text-2xl text-foreground">Order History</h2>
        <p className="mt-2 text-sm text-slate-700">
          Unified view of inbound and outbound stock movements, newest first.
        </p>

        <label className="mt-4 inline-block text-sm">
          <span className="mr-2 font-semibold text-slate-700">Movement type</span>
          <select
            value={movementFilter}
            onChange={(event) => setMovementFilter(event.target.value as "all" | "inbound" | "outbound")}
            className="rounded-lg border border-line bg-panel px-2 py-1"
          >
            <option value="all">All</option>
            <option value="inbound">Inbound</option>
            <option value="outbound">Outbound</option>
          </select>
        </label>

        <div className="mt-4">
          {loading ? (
            <StateMessage tone="loading" title="Loading order history…" />
          ) : loadError ? (
            <StateMessage tone="error" title="Could not load orders" description={loadError} />
          ) : filteredOrders.length === 0 ? (
            <StateMessage tone="empty" title="No movements recorded yet." />
          ) : (
            <div className="overflow-x-auto">
              <table className="mt-2 w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase tracking-wide text-slate-600">
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2 pr-4">SKU</th>
                    <th className="py-2 pr-4">Product</th>
                    <th className="py-2 pr-4">Quantity</th>
                    <th className="py-2 pr-4">Warehouse</th>
                    <th className="py-2 pr-4">Reference / Tracking</th>
                    <th className="py-2 pr-4">Created</th>
                    <th className="py-2 pr-4">User</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOrders.map((order) => (
                    <tr key={`${order.movement_type}-${order.id}`} className="border-b border-line/60">
                      <td className="py-2 pr-4">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                            order.movement_type === "inbound"
                              ? "bg-accent-soft text-accent-strong"
                              : "bg-panel-soft text-slate-700"
                          }`}
                        >
                          {order.movement_type}
                          {order.exit_type ? ` (${order.exit_type})` : ""}
                        </span>
                      </td>
                      <td className="py-2 pr-4 font-semibold text-foreground">{order.sku}</td>
                      <td className="py-2 pr-4">{order.name}</td>
                      <td className="py-2 pr-4">{order.quantity}</td>
                      <td className="py-2 pr-4">{order.warehouse}</td>
                      <td className="py-2 pr-4">{order.reference ?? order.tracking_number ?? "—"}</td>
                      <td className="py-2 pr-4">{new Date(order.created_at).toLocaleString()}</td>
                      <td className="py-2 pr-4 font-mono text-xs break-all">{order.user_uuid}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
