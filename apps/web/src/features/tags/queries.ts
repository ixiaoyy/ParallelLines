import { useQuery } from "@tanstack/vue-query";

import { TAXONOMY_QUERY_GC_TIME_MS, TAXONOMY_QUERY_STALE_TIME_MS } from "@/shared/api/queryClient";
import { queryKeys } from "@/shared/api/queryKeys";

import { fetchTags } from "./api";
import { toTagItem } from "./model";

export function useTags(limit = 30) {
  return useQuery({
    queryKey: queryKeys.tags(limit),
    queryFn: async () => (await fetchTags(limit)).map(toTagItem),
    staleTime: TAXONOMY_QUERY_STALE_TIME_MS,
    gcTime: TAXONOMY_QUERY_GC_TIME_MS,
  });
}
