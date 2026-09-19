"use client";

import { useEffect, useState } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { StateMessage } from "@/components/ui/StateMessage";
import { ApiError } from "@/lib/api-client";
import {
  getWeeklyWarehouseClientPerformance,
  type WeeklyPerformanceEntry,
} from "@/lib/reporting";

export default function ReportingPage() {
  return (
    <RequireAuth>
      <ReportingPageContent />
    </RequireAuth>
  );
}

function ReportingPageContent() {
  const [entries, setEntries] = useState<WeeklyPerformanceEntry[]>([]);
  const [weekStart, setWeekStart] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    getWeeklyWarehouseClientPerformance()
      .then((response) => {
        setWeekStart(response.week_start);
        setEntries(response.entries);
      })
      .catch((error) => {
        setLoadError(
          error instanceof ApiError ? error.message : "Unable to load weekly performance."
        );
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="space-y-6">
      <div className="dashboard-card p-6">
        <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent-strong">
              TrackFlow business reporting
            </p>
            <h2 className="mt-1 font-display text-2xl text-foreground">
              Weekly warehouse performance
            </h2>
            <p className="mt-2 text-sm text-slate-700">
              Warehouse and client operating KPIs for the latest completed reporting week.
            </p>
          </div>
          {weekStart ? (
            <p className="text-sm font-semibold text-slate-700">
              Reporting week: <span className="text-foreground">{weekStart}</span>
            </p>
          ) : null}
        </div>

        <div className="mt-6">
          {loading ? (
            <StateMessage tone="loading" title="Loading weekly performance…" />
          ) : loadError ? (
            <StateMessage
              tone="error"
              title="Could not load weekly performance"
              description={loadError}
            />
          ) : entries.length === 0 ? (
            <StateMessage
              tone="empty"
              title="No weekly performance reported yet."
              description="Run the weekly reporting pipeline to populate this view."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-line text-xs uppercase tracking-wide text-slate-600">
                    <th className="py-2 pr-4">Reporting Week</th>
                    <th className="py-2 pr-4">Warehouse</th>
                    <th className="py-2 pr-4">Client</th>
                    <th className="py-2 pr-4">Inbound Volume</th>
                    <th className="py-2 pr-4">Outbound Throughput</th>
                    <th className="py-2 pr-4">Stockout Frequency</th>
                    <th className="py-2 pr-4">Discrepancy Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr
                      key={`${entry.week_start}-${entry.warehouse}-${entry.client_id}`}
                      className="border-b border-line/60"
                    >
                      <td className="py-3 pr-4">{entry.week_start}</td>
                      <td className="py-3 pr-4 font-semibold text-foreground">{entry.warehouse}</td>
                      <td className="py-3 pr-4">{entry.client_id}</td>
                      <td className="py-3 pr-4">{entry.inbound_units_count}</td>
                      <td className="py-3 pr-4">{entry.outbound_orders_count}</td>
                      <td className="py-3 pr-4">{entry.stockout_events_count}</td>
                      <td className="py-3 pr-4">{(entry.discrepancy_rate * 100).toFixed(1)}%</td>
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
