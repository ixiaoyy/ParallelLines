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

export function useExportDataExplorerReport() {
  return useMutation<Blob, Error, { reportId: string; params: AnalyticsRangeParams }>({
    mutationFn: ({ reportId, params }) => exportDataExplorerReport(reportId, params),
  });
}
