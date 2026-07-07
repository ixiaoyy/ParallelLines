import type { components } from "@/shared/api/generated";

export type AnalyticsOverview = components["schemas"]["AnalyticsOverviewResponse"];
export type AnalyticsMetricPoint = components["schemas"]["AnalyticsMetricPoint"];

const SOURCE_TYPE_LABELS: Record<string, string> = {
  campaign: "活动投放",
  direct: "直接访问",
  internal: "站内跳转",
  referral: "外部链接",
  search: "搜索引擎",
  social: "社交媒体",
};

const SOURCE_NAME_LABELS: Record<string, string> = {
  Direct: "直接访问",
  Internal: "站内跳转",
};

// Formats a metric with the product's Chinese numeric grouping.
// Key parameter `value` is an optional metric number. Return value is display text. Side effect: none.
export function formatMetric(value: number | undefined): string {
  return new Intl.NumberFormat("zh-CN").format(value ?? 0);
}

// Converts backend traffic source types into Chinese labels for dashboards and reports.
// Key parameter `sourceType` is the backend enum-like source value. Return value is display text. Side effect: none.
export function sourceTypeLabel(sourceType: string): string {
  return SOURCE_TYPE_LABELS[sourceType] ?? sourceType;
}

// Converts backend traffic source names into Chinese labels where the backend stores English defaults.
// Key parameter `sourceName` is the stored source display name. Return value is localized text. Side effect: none.
export function sourceNameLabel(sourceName: string): string {
  return SOURCE_NAME_LABELS[sourceName] ?? sourceName;
}
