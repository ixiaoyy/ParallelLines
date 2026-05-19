import { useQuery } from "@tanstack/vue-query";

import { queryKeys } from "@/shared/api/queryKeys";

import { fetchTags } from "./api";
import { toTagItem } from "./model";

export function useTags(limit = 30) {
  return useQuery({
    queryKey: queryKeys.tags(limit),
    queryFn: async () => (await fetchTags(limit)).map(toTagItem),
    staleTime: 60_000,
  });
}
