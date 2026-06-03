import { useQuery } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { TAXONOMY_QUERY_GC_TIME_MS, TAXONOMY_QUERY_STALE_TIME_MS } from "@/shared/api/queryClient";
import { queryKeys } from "@/shared/api/queryKeys";

import { fetchTags } from "./api";
import { toTagItem } from "./model";

// Fetches public tag taxonomy for visible navigation/filter surfaces.
// Key parameters: `limit` caps results and `enabled` gates hidden consumers; return value is Vue Query tag list state.
export function useTags(limit = 30, enabled: MaybeRefOrGetter<boolean> = true) {
  return useQuery({
    queryKey: queryKeys.tags(limit),
    queryFn: async () => (await fetchTags(limit)).map(toTagItem),
    enabled: computed(() => Boolean(toValue(enabled))),
    staleTime: TAXONOMY_QUERY_STALE_TIME_MS,
    gcTime: TAXONOMY_QUERY_GC_TIME_MS,
  });
}
