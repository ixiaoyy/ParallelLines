import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import { fetchMigrationExport, previewMigrationImport, runMigrationImport } from "./api";
import type { MigrationExportResponse, MigrationImportRequest, MigrationImportResponse } from "./model";

export function usePreviewMigrationImport() {
  return useMutation<MigrationImportResponse, Error, MigrationImportRequest>({
    mutationFn: previewMigrationImport,
  });
}

export function useRunMigrationImport() {
  const queryClient = useQueryClient();
  return useMutation<MigrationImportResponse, Error, MigrationImportRequest>({
    mutationFn: runMigrationImport,
    onSuccess: async (result) => {
      if (result.created || result.updated) {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: queryKeys.adminRoot }),
          queryClient.invalidateQueries({ queryKey: queryKeys.usersRoot }),
          queryClient.invalidateQueries({ queryKey: queryKeys.topicsRoot }),
          queryClient.invalidateQueries({ queryKey: queryKeys.userRelationshipUsersRoot }),
        ]);
      }
    },
  });
}

export function useMigrationExport(enabled = false) {
  return useQuery<MigrationExportResponse, Error>({
    queryKey: queryKeys.adminMigrationExport,
    queryFn: fetchMigrationExport,
    enabled: computed(() => enabled && hasAccessToken()),
    retry: false,
  });
}
