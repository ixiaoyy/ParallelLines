import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";
import type {
  BadgeGrantRequest,
  BadgeResponse,
  BadgeRevokeRequest,
} from "@/features/badges/model";

import {
  createAdminApiKey,
  createAdminWebhook,
  disableAdminApiKey,
  disableAdminWebhook,
  fetchAdminApiKeys,
  fetchAdminBadges,
  fetchAdminAuditLogs,
  fetchAdminEmailLogs,
  fetchAdminSettings,
  fetchAdminSystem,
  fetchAdminUsers,
  fetchAdminWebhookDeliveries,
  fetchAdminWebhooks,
  fetchPublicSiteSettings,
  grantAdminUserBadge,
  revokeAdminUserBadge,
  updateAdminSetting,
  updateAdminUser,
} from "./api";
import type {
  AdminEmailLogResponse,
  ApiKeyCreateRequest,
  ApiKeyCreateResponse,
  ApiKeyResponse,
  AdminSystemOverviewResponse,
  AdminUserResponse,
  AdminUsersParams,
  AdminUserUpdateRequest,
  AuditLogResponse,
  PublicSiteSettingsResponse,
  SiteSettingResponse,
  SiteSettingUpdateRequest,
  WebhookDeliveryResponse,
  WebhookEndpointCreateRequest,
  WebhookEndpointCreateResponse,
  WebhookEndpointResponse,
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

export function useAdminBadges() {
  return useQuery<BadgeResponse[], Error>({
    queryKey: queryKeys.adminBadges,
    queryFn: fetchAdminBadges,
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 60_000,
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

export function useGrantAdminUserBadge() {
  const queryClient = useQueryClient();
  return useMutation<AdminUserResponse, Error, { userId: string; payload: BadgeGrantRequest }>({
    mutationFn: ({ userId, payload }) => grantAdminUserBadge(userId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminRoot });
    },
  });
}

export function useRevokeAdminUserBadge() {
  const queryClient = useQueryClient();
  return useMutation<
    AdminUserResponse,
    Error,
    { userId: string; badgeSlug: string; payload: BadgeRevokeRequest }
  >({
    mutationFn: ({ userId, badgeSlug, payload }) =>
      revokeAdminUserBadge(userId, badgeSlug, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminRoot });
    },
  });
}

export function useAdminApiKeys() {
  return useQuery<ApiKeyResponse[], Error>({
    queryKey: queryKeys.adminApiKeys,
    queryFn: fetchAdminApiKeys,
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 15_000,
  });
}

export function useCreateAdminApiKey() {
  const queryClient = useQueryClient();
  return useMutation<ApiKeyCreateResponse, Error, ApiKeyCreateRequest>({
    mutationFn: createAdminApiKey,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminApiKeys });
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminRoot });
    },
  });
}

export function useDisableAdminApiKey() {
  const queryClient = useQueryClient();
  return useMutation<ApiKeyResponse, Error, string>({
    mutationFn: disableAdminApiKey,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminApiKeys });
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminRoot });
    },
  });
}

export function useAdminWebhooks() {
  return useQuery<WebhookEndpointResponse[], Error>({
    queryKey: queryKeys.adminWebhooks,
    queryFn: fetchAdminWebhooks,
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 15_000,
  });
}

export function useCreateAdminWebhook() {
  const queryClient = useQueryClient();
  return useMutation<WebhookEndpointCreateResponse, Error, WebhookEndpointCreateRequest>({
    mutationFn: createAdminWebhook,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminWebhooks });
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminRoot });
    },
  });
}

export function useDisableAdminWebhook() {
  const queryClient = useQueryClient();
  return useMutation<WebhookEndpointResponse, Error, string>({
    mutationFn: disableAdminWebhook,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminWebhooks });
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminRoot });
    },
  });
}

export function useAdminWebhookDeliveries() {
  return useQuery<WebhookDeliveryResponse[], Error>({
    queryKey: queryKeys.adminWebhookDeliveries,
    queryFn: () => fetchAdminWebhookDeliveries(),
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 10_000,
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
