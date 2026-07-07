import { apiGet, createApiHeaders, getApiUrl } from "@/shared/api/client";

import type { AnalyticsOverview } from "./model";

export interface AnalyticsRangeParams {
  startDate: string;
  endDate: string;
}

export interface SiteVisitPayload {
  path: string;
  title?: string | null;
  referrer?: string | null;
}

function rangeQuery(params: AnalyticsRangeParams) {
  const query = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
  });
  return query.toString();
}

export function fetchAnalyticsOverview(params: AnalyticsRangeParams): Promise<AnalyticsOverview> {
  return apiGet<AnalyticsOverview>(`/admin/analytics?${rangeQuery(params)}`);
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
