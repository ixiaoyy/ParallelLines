import { useQuery } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import { fetchAnalyticsOverview } from "./api";
import type { AnalyticsRangeParams } from "./api";
import type { AnalyticsOverview } from "./model";

export function useAnalyticsOverview(
  params: MaybeRefOrGetter<AnalyticsRangeParams>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery<AnalyticsOverview | null, Error>({
    queryKey: computed(() => {
      const range = toValue(params);
      return queryKeys.adminAnalytics(range.startDate, range.endDate);
    }),
    queryFn: async () => {
      if (!hasAccessToken()) {
        return null;
      }
      return fetchAnalyticsOverview(toValue(params));
    },
    enabled: computed(() => toValue(enabled)),
    staleTime: 30_000,
  });
}
