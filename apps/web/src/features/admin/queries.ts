import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  fetchAdminAuditLogs,
  fetchAdminEmailLogs,
  fetchAdminSettings,
  fetchAdminSystem,
  fetchAdminUsers,
  fetchPublicSiteSettings,
  updateAdminSetting,
  updateAdminUser,
} from "./api";
import type {
  AdminEmailLogResponse,
  AdminSystemOverviewResponse,
  AdminUserResponse,
  AdminUsersParams,
  AdminUserUpdateRequest,
  AuditLogResponse,
  PublicSiteSettingsResponse,
  SiteSettingResponse,
  SiteSettingUpdateRequest,
} from "./model";

export function usePublicSiteSettings() {
  return useQuery<PublicSiteSettingsResponse, Error>({
    queryKey: queryKeys.siteSettingsPublic,
    queryFn: fetchPublicSiteSettings,
    retry: false,
    staleTime: 300_000,
  });
}

export function useAdminSettings() {
  return useQuery<SiteSettingResponse[], Error>({
    queryKey: queryKeys.adminSettings,
    queryFn: fetchAdminSettings,
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 30_000,
  });
}

export function useUpdateAdminSetting() {
  const queryClient = useQueryClient();
  return useMutation<SiteSettingResponse, Error, { key: string; payload: SiteSettingUpdateRequest }>({
    mutationFn: ({ key, payload }) => updateAdminSetting(key, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminRoot });
      await queryClient.invalidateQueries({ queryKey: queryKeys.siteSettingsPublic });
    },
  });
}

export function useAdminUsers(params: MaybeRefOrGetter<AdminUsersParams>) {
  return useQuery<AdminUserResponse[], Error>({
    queryKey: computed(() => queryKeys.adminUsers(toValue(params))),
    queryFn: () => fetchAdminUsers(toValue(params)),
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 15_000,
  });
}

export function useUpdateAdminUser() {
  const queryClient = useQueryClient();
  return useMutation<AdminUserResponse, Error, { userId: string; payload: AdminUserUpdateRequest }>({
    mutationFn: ({ userId, payload }) => updateAdminUser(userId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminRoot });
    },
  });
}

export function useAdminSystem() {
  return useQuery<AdminSystemOverviewResponse, Error>({
    queryKey: queryKeys.adminSystem,
    queryFn: fetchAdminSystem,
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 15_000,
  });
}

export function useAdminAuditLogs() {
  return useQuery<AuditLogResponse[], Error>({
    queryKey: queryKeys.adminAudit,
    queryFn: () => fetchAdminAuditLogs(),
    enabled: computed(() => hasAccessToken()),
    retry: false,
  });
}

export function useAdminEmailLogs() {
  return useQuery<AdminEmailLogResponse[], Error>({
    queryKey: queryKeys.adminEmailLogs,
    queryFn: () => fetchAdminEmailLogs(),
    enabled: computed(() => hasAccessToken()),
    retry: false,
  });
}
