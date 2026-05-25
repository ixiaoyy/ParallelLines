import type { components } from "@/shared/api/generated";

export type AnalyticsOverview = components["schemas"]["AnalyticsOverviewResponse"];
export type AnalyticsMetricPoint = components["schemas"]["AnalyticsMetricPoint"];
export type DataExplorerReport = components["schemas"]["DataExplorerReportResponse"];
export type DataExplorerReportSummary = components["schemas"]["DataExplorerReportSummary"];

export function formatMetric(value: number | undefined): string {
  return new Intl.NumberFormat("zh-CN").format(value ?? 0);
}

export function reportCell(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "number") {
    return formatMetric(value);
  }
  return String(value);
}
