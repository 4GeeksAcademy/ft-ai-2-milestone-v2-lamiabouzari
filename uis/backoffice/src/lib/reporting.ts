import { apiRequest } from "@/lib/api-client";

export interface WeeklyPerformanceEntry {
  week_start: string;
  warehouse: string;
  client_id: string;
  inbound_units_count: number;
  outbound_orders_count: number;
  stockout_events_count: number;
  discrepancy_rate: number;
}

export interface PipelineRunSummary {
  status: string;
  records_processed: number;
  week_start: string;
  week_end: string;
}

export interface SourceGap {
  source_events: number;
  missing_client_id: number;
  missing_warehouse: number;
}

export interface WeeklyPerformanceResponse {
  week_start: string | null;
  entries: WeeklyPerformanceEntry[];
  report_state: "never_run" | "completed_without_rows" | "ready";
  pipeline_run?: PipelineRunSummary;
  source_gap?: SourceGap;
}

export function getWeeklyWarehouseClientPerformance(): Promise<WeeklyPerformanceResponse> {
  return apiRequest<WeeklyPerformanceResponse>(
    "/reporting/weekly-warehouse-client-performance",
    { auth: true }
  );
}
