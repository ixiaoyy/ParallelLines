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

// Serializes a selected analytics date range plus optional report limits.
// Key parameters are the inclusive `params` range and optional extra query values; return value is a URL query string. Side effect: none.
function rangeQuery(params: AnalyticsRangeParams, extra?: Record<string, string | number>): string {
  const query = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
  });
  Object.entries(extra ?? {}).forEach(([key, value]) => query.set(key, String(value)));
  return query.toString();
}

// Fetches the real analytics overview for one inclusive date range.
// Key parameter `params` contains start and end dates; return value is the generated overview DTO. Side effect: authenticated GET request.
export function fetchAnalyticsOverview(params: AnalyticsRangeParams): Promise<AnalyticsOverview> {
  return apiGet<AnalyticsOverview>(`/admin/analytics?${rangeQuery(params)}`);
}

// Fetches backend-owned safe Data Explorer report presets.
// Key parameters: none. Return value is the generated report summary DTO list. Side effect: authenticated GET request.
export function fetchDataExplorerReports(): Promise<DataExplorerReportSummary[]> {
  return apiGet<DataExplorerReportSummary[]>("/admin/analytics/reports");
}

// Runs one backend-owned Data Explorer preset for the selected date range.
// Key parameters are a report ID and date range; return value is the generated report DTO. Side effect: authenticated GET request.
export function runDataExplorerReport(
  reportId: string,
  params: AnalyticsRangeParams,
): Promise<DataExplorerReport> {
  return apiGet<DataExplorerReport>(
    `/admin/analytics/reports/${encodeURIComponent(reportId)}?${rangeQuery(params, { limit: 100 })}`,
  );
}

// Downloads a Data Explorer CSV with auth headers so permission checks and audit logging remain active.
// Key parameters are a report ID and date range; return value is the CSV Blob. Side effect: authenticated fetch request.
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
