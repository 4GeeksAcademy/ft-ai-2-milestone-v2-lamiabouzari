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

interface WeeklyPerformanceResponse {
  week_start: string | null;
  entries: WeeklyPerformanceEntry[];
}

export function getWeeklyWarehouseClientPerformance(): Promise<WeeklyPerformanceResponse> {
  return apiRequest<WeeklyPerformanceResponse>(
    "/reporting/weekly-warehouse-client-performance",
    { auth: true }
  );
}
