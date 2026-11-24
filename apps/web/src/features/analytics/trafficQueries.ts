import { useQuery } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { fetchTrafficOverview } from "./trafficApi";
import type { TrafficRangeParams } from "./trafficApi";
import type { TrafficOverview } from "./trafficModel";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

/** 日期和站点共同隔离缓存；仅进入或主动操作时读取，不轮询、不因切换窗口或重连重刷。 */
export function useTrafficOverview(
  params: MaybeRefOrGetter<TrafficRangeParams>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery<TrafficOverview | null, Error>({
    queryKey: computed(() => {
      const range = toValue(params);
      return queryKeys.adminTraffic(range.startDate, range.endDate, range.siteKey);
    }),
    queryFn: ({ signal }) => {
      if (!hasAccessToken()) return null;
      return fetchTrafficOverview(toValue(params), signal);
    },
    enabled: computed(() => toValue(enabled)),
    staleTime: 300_000,
    retry: false,
    refetchInterval: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}
