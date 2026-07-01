import { apiGet, createApiHeaders, getApiUrl } from "@/shared/api/client";

import type { AnalyticsOverview, DataExplorerReport, DataExplorerReportSummary } from "./model";

export interface AnalyticsRangeParams {
  startDate: string;
  endDate: string;
}

export interface SiteVisitPayload {
  path: string;
  title?: string | null;
  referrer?: string | null;
}

function rangeQuery(params: AnalyticsRangeParams, extra?: Record<string, string | number>) {
  const query = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
  });
  Object.entries(extra ?? {}).forEach(([key, value]) => query.set(key, String(value)));
  return query.toString();
}

export function fetchAnalyticsOverview(params: AnalyticsRangeParams): Promise<AnalyticsOverview> {
  return apiGet<AnalyticsOverview>(`/admin/analytics?${rangeQuery(params)}`);
}

export function fetchDataExplorerReports(): Promise<DataExplorerReportSummary[]> {
  return apiGet<DataExplorerReportSummary[]>("/admin/analytics/reports");
}

export function runDataExplorerReport(
  reportId: string,
  params: AnalyticsRangeParams,
): Promise<DataExplorerReport> {
  return apiGet<DataExplorerReport>(
    `/admin/analytics/reports/${encodeURIComponent(reportId)}?${rangeQuery(params, { limit: 100 })}`,
  );
}

export async function exportDataExplorerReport(
  reportId: string,
  params: AnalyticsRangeParams,
): Promise<Blob> {
  const response = await fetch(
    getApiUrl(
      `/admin/analytics/reports/${encodeURIComponent(reportId)}/export.csv?${rangeQuery(params)}`,
    ),
    { headers: createApiHeaders() },
  );
  if (!response.ok) {
    throw new Error("analytics_export_failed");
  }
  return response.blob();
}

// Sends a browser page-view event without involving the global request loading state.
// Key parameter `payload` is the current route path/title/referrer. Return value is none.
// Side effect: performs a fire-and-forget analytics POST.
export async function recordSiteVisit(payload: SiteVisitPayload): Promise<void> {
  const response = await fetch(getApiUrl("/site/visits"), {
    method: "POST",
    headers: createApiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
    keepalive: true,
  });
  if (!response.ok) {
    throw new Error("site_visit_record_failed");
  }
}
