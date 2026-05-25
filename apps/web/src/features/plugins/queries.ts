import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import { fetchAdminPlugins, fetchSiteExtensions, updateAdminPlugin } from "./api";
import type { PluginInfo, PluginUiExtension, PluginUpdateRequest } from "./model";

export function useSiteExtensions() {
  return useQuery<PluginUiExtension[], Error>({
    queryKey: queryKeys.siteExtensions,
    queryFn: fetchSiteExtensions,
    retry: false,
    staleTime: 120_000,
  });
}

export function useAdminPlugins() {
  return useQuery<PluginInfo[], Error>({
    queryKey: queryKeys.adminPlugins,
    queryFn: fetchAdminPlugins,
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 30_000,
  });
}

export function useUpdateAdminPlugin() {
  const queryClient = useQueryClient();
  return useMutation<PluginInfo, Error, { pluginId: string; payload: PluginUpdateRequest }>({
    mutationFn: ({ pluginId, payload }) => updateAdminPlugin(pluginId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminPlugins });
      await queryClient.invalidateQueries({ queryKey: queryKeys.siteExtensions });
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminRoot });
    },
  });
}
