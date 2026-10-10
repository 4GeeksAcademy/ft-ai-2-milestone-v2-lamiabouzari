"use client";

import { useEffect, useState } from "react";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { StateMessage } from "@/components/ui/StateMessage";
import { ApiError } from "@/lib/api-client";
import {
  getWeeklyWarehouseClientPerformance,
  type PipelineRunSummary,
  type SourceGap,
  type WeeklyPerformanceEntry,
} from "@/lib/reporting";

export default function ReportingPage() {
  return (
    <RequireAuth>
      <ReportingPageContent />
    </RequireAuth>
  );
}

function zeroRowDescription(
  run: PipelineRunSummary,
  gap: SourceGap | undefined
): string {
  const processed = `${run.records_processed} KPI ${run.records_processed === 1 ? "row" : "rows"}`;
  if (!gap || gap.source_events === 0) {
    return `The recorded run for ${run.week_start} completed with ${processed}. That week has no inbound, outbound, stockout, or discrepancy events.`;
  }
  if (gap.missing_client_id === gap.source_events && gap.missing_warehouse === 0) {
    return `The recorded run for ${run.week_start} completed with ${processed}. It read ${gap.source_events} source events. Each event includes a warehouse, and none includes client_id, so the pipeline cannot group them into a warehouse and client row.`;
  }
  return `The recorded run for ${run.week_start} completed with ${processed}. Of ${gap.source_events} source events, ${gap.missing_client_id} are missing client_id and ${gap.missing_warehouse} are missing a warehouse.`;
}

function ReportingPageContent() {
  const [entries, setEntries] = useState<WeeklyPerformanceEntry[]>([]);
  const [weekStart, setWeekStart] = useState<string | null>(null);
  const [reportState, setReportState] = useState<
    "never_run" | "completed_without_rows" | "ready"
  >("never_run");
  const [pipelineRun, setPipelineRun] = useState<PipelineRunSummary | null>(null);
  const [sourceGap, setSourceGap] = useState<SourceGap | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    getWeeklyWarehouseClientPerformance()
      .then((response) => {
        setWeekStart(response.week_start);
        setEntries(response.entries);
        setReportState(response.report_state);
        setPipelineRun(response.pipeline_run ?? null);
        setSourceGap(response.source_gap ?? null);
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
          ) : reportState === "completed_without_rows" && pipelineRun ? (
            <StateMessage
              tone="empty"
              title="The weekly pipeline completed with no valid rows."
              description={zeroRowDescription(pipelineRun, sourceGap ?? undefined)}
            />
          ) : entries.length === 0 ? (
            <StateMessage
              tone="empty"
              title="No weekly performance reported yet."
              description="The weekly pipeline has not been run."
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
