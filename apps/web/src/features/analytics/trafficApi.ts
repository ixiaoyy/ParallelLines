import type { AnalyticsRangeParams } from "./api";
import type { TrafficOverview, TrafficSiteFilter } from "./trafficModel";

import { apiGet } from "@/shared/api/client";

export interface TrafficRangeParams extends AnalyticsRangeParams {
  siteKey: TrafficSiteFilter;
}

/** 读取服务端缓存的跨站流量；使用查询取消信号与 15 秒总超时，不触发汇总或强制绕过缓存。 */
export async function fetchTrafficOverview(
  params: TrafficRangeParams,
  signal?: AbortSignal,
): Promise<TrafficOverview> {
  const query = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
    site_key: params.siteKey,
  });
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  const timeout = window.setTimeout(abort, 15_000);
  try {
    return await apiGet<TrafficOverview>(`/admin/analytics/traffic?${query}`, {
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
  }
}
