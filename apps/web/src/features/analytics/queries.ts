import { useMutation, useQuery } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  exportDataExplorerReport,
  fetchAnalyticsOverview,
  fetchDataExplorerReports,
  runDataExplorerReport,
} from "./api";
import type { AnalyticsRangeParams } from "./api";
import type { AnalyticsOverview, DataExplorerReport, DataExplorerReportSummary } from "./model";

// Loads the real analytics overview with a cache key scoped to the selected date range.
// Key parameters are range refs and an enabled flag; return value is a TanStack query. Side effect: authenticated GET when enabled.
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

// Loads backend-owned safe Data Explorer report presets when the explorer is opened.
// Key parameter `enabled` controls lazy loading; return value is a TanStack query. Side effect: authenticated GET when enabled.
export function useDataExplorerReports(enabled: MaybeRefOrGetter<boolean> = true) {
  return useQuery<DataExplorerReportSummary[], Error>({
    queryKey: queryKeys.adminAnalyticsReports,
    queryFn: async () => {
      if (!hasAccessToken()) {
        return [];
      }
      return fetchDataExplorerReports();
    },
    enabled: computed(() => toValue(enabled)),
    staleTime: 60_000,
  });
}

// Runs one safe preset and scopes its cache entry to report ID plus date range.
// Key parameters are report ID, range, and enabled refs; return value is a TanStack query. Side effect: authenticated GET when enabled.
export function useDataExplorerReport(
  reportId: MaybeRefOrGetter<string>,
  params: MaybeRefOrGetter<AnalyticsRangeParams>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery<DataExplorerReport | null, Error>({
    queryKey: computed(() => {
      const range = toValue(params);
      return queryKeys.adminAnalyticsReport(toValue(reportId), range.startDate, range.endDate);
    }),
    queryFn: async () => {
      const id = toValue(reportId);
      if (!id || !hasAccessToken()) {
        return null;
      }
      return runDataExplorerReport(id, toValue(params));
    },
    enabled: computed(() => Boolean(toValue(reportId)) && toValue(enabled)),
    staleTime: 30_000,
  });
}

// Exposes the authenticated CSV export as a mutation so pending and error states remain visible.
// Key parameters: none. Return value is a TanStack mutation. Side effect: authenticated CSV request when invoked.
export function useExportDataExplorerReport() {
  return useMutation<Blob, Error, { reportId: string; params: AnalyticsRangeParams }>({
    mutationFn: ({ reportId, params }) => exportDataExplorerReport(reportId, params),
  });
}
