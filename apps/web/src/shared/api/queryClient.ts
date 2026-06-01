import { QueryClient } from "@tanstack/vue-query";

export const HOT_QUERY_STALE_TIME_MS = 30_000;
export const HOT_QUERY_GC_TIME_MS = 10 * 60_000;
export const TAXONOMY_QUERY_STALE_TIME_MS = 10 * 60_000;
export const TAXONOMY_QUERY_GC_TIME_MS = 30 * 60_000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: HOT_QUERY_STALE_TIME_MS,
      gcTime: HOT_QUERY_GC_TIME_MS,
      refetchOnWindowFocus: false,
    },
  },
});
