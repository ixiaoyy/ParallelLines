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
  collectFrontierNews,
  collectFrontierNewsSource,
  createFrontierNewsSource,
  createAdminApiKey,
  createAdminWebhook,
  deleteFrontierNewsSource,
  disableAdminApiKey,
  disableAdminWebhook,
  enrichFrontierNewsItem,
  fetchAdminApiKeys,
  fetchAdminBadges,
  fetchAdminFableSpaceAccessGrants,
  fetchAdminAuditLogs,
  fetchAdminEmailLogs,
  fetchAdminSystem,
  fetchAdminUsers,
  fetchAdminWebhookDeliveries,
  fetchAdminWebhooks,
  fetchFrontierNewsItems,
  fetchFrontierNewsSources,
  fetchPublicSiteSettings,
  grantAdminUserBadge,
  queueFrontierNewsItem,
  revokeAdminFableSpaceAccessGrant,
  revokeAdminUserBadge,
  updateFrontierNewsSource,
  updateAdminFableSpaceAccessGrant,
  updateAdminUser,
} from "./api";
import type {
  AdminEmailLogResponse,
  AdminFableSpaceAccessGrantResponse,
  AdminFableSpaceAccessGrantsParams,
  AdminFableSpaceAccessGrantUpdateRequest,
  ApiKeyCreateRequest,
  ApiKeyCreateResponse,
  ApiKeyResponse,
  AdminSystemOverviewResponse,
  AdminUserResponse,
  AdminUsersParams,
  AdminUserUpdateRequest,
  AuditLogResponse,
  FrontierNewsCollectResponse,
  FrontierNewsItemResponse,
  FrontierNewsItemsParams,
  FrontierNewsSourceCreateRequest,
  FrontierNewsSourceResponse,
  FrontierNewsSourceUpdateRequest,
  PublicSiteSettingsResponse,
  WebhookDeliveryResponse,
  WebhookEndpointCreateRequest,
  WebhookEndpointCreateResponse,
  WebhookEndpointResponse,
} from "./model";
import {
  cachePublicSiteSettings,
  readCachedPublicSiteSettings,
} from "./publicSettingsCache";

export function usePublicSiteSettings() {
  return useQuery<PublicSiteSettingsResponse, Error>({
    queryKey: queryKeys.siteSettingsPublic,
    queryFn: async () => {
      const settings = await fetchPublicSiteSettings();
      cachePublicSiteSettings(settings);
      return settings;
    },
    placeholderData: () => readCachedPublicSiteSettings() ?? undefined,
    retry: false,
    staleTime: 300_000,
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

// Provides a reactive admin search over forum users and their FableSpace entitlement state.
// `params` may be a ref/getter and drives both the cache key and request. Return value is the Vue Query result; side effect: fetches when authenticated.
export function useAdminFableSpaceAccessGrants(
  params: MaybeRefOrGetter<AdminFableSpaceAccessGrantsParams>,
) {
  return useQuery<AdminFableSpaceAccessGrantResponse[], Error>({
    queryKey: computed(() => queryKeys.adminFableSpaceAccessGrants(toValue(params))),
    queryFn: () => fetchAdminFableSpaceAccessGrants(toValue(params)),
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 15_000,
  });
}

// Creates or updates an entitlement and refreshes admin plus current-user access caches.
// Parameters: none at setup. Return value is a mutation accepting userId and grant payload; side effect: PUT plus cache invalidation on success.
export function useUpdateAdminFableSpaceAccessGrant() {
  const queryClient = useQueryClient();
  return useMutation<
    AdminFableSpaceAccessGrantResponse,
    Error,
    { userId: string; payload: AdminFableSpaceAccessGrantUpdateRequest }
  >({
    mutationFn: ({ userId, payload }) => updateAdminFableSpaceAccessGrant(userId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.adminRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.fableSpaceAccess }),
      ]);
    },
  });
}

// Revokes an entitlement and refreshes admin plus current-user access caches.
// Parameters: none at setup. Return value is a mutation accepting a user ID; side effect: DELETE plus cache invalidation on success.
export function useRevokeAdminFableSpaceAccessGrant() {
  const queryClient = useQueryClient();
  return useMutation<AdminFableSpaceAccessGrantResponse, Error, string>({
    mutationFn: revokeAdminFableSpaceAccessGrant,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.adminRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.fableSpaceAccess }),
      ]);
    },
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

/**
 * Provides cached frontier source rows for the admin operations panel.
 *
 * @returns Vue Query result containing white-listed source rows.
 */
export function useFrontierNewsSources() {
  return useQuery<FrontierNewsSourceResponse[], Error>({
    queryKey: queryKeys.adminFrontierNewsSources,
    queryFn: fetchFrontierNewsSources,
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 30_000,
  });
}

/**
 * Creates a frontier source and invalidates all frontier admin caches.
 *
 * @returns Mutation whose variables are the source creation payload.
 */
export function useCreateFrontierNewsSource() {
  const queryClient = useQueryClient();
  return useMutation<FrontierNewsSourceResponse, Error, FrontierNewsSourceCreateRequest>({
    mutationFn: createFrontierNewsSource,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminFrontierNewsRoot });
    },
  });
}

/**
 * Updates one frontier source and refreshes source/material views afterward.
 *
 * @returns Mutation accepting sourceId plus a partial update payload.
 */
export function useUpdateFrontierNewsSource() {
  const queryClient = useQueryClient();
  return useMutation<
    FrontierNewsSourceResponse,
    Error,
    { sourceId: string; payload: FrontierNewsSourceUpdateRequest }
  >({
    mutationFn: ({ sourceId, payload }) => updateFrontierNewsSource(sourceId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminFrontierNewsRoot });
    },
  });
}

/**
 * Deletes one frontier source and refreshes the source/material views afterward.
 *
 * @returns Mutation accepting the source ID to remove.
 */
export function useDeleteFrontierNewsSource() {
  const queryClient = useQueryClient();
  return useMutation<FrontierNewsSourceResponse, Error, string>({
    mutationFn: deleteFrontierNewsSource,
    onSuccess: async (deletedSource) => {
      queryClient.setQueryData<FrontierNewsSourceResponse[]>(
        queryKeys.adminFrontierNewsSources,
        (current) => current?.filter((source) => source.id !== deletedSource.id) ?? current,
      );
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminFrontierNewsRoot });
    },
  });
}

/**
 * Runs a manual all-source collection and refreshes frontier/moderation caches.
 *
 * @returns Mutation resolving to backend collection counters.
 */
export function useCollectFrontierNews() {
  const queryClient = useQueryClient();
  return useMutation<FrontierNewsCollectResponse, Error, void>({
    mutationFn: () => collectFrontierNews(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminFrontierNewsRoot });
      await queryClient.invalidateQueries({ queryKey: queryKeys.moderationRoot });
    },
  });
}

/**
 * Runs a manual collection for a single source and refreshes dependent queues.
 *
 * @returns Mutation accepting the source ID to collect.
 */
export function useCollectFrontierNewsSource() {
  const queryClient = useQueryClient();
  return useMutation<FrontierNewsCollectResponse, Error, string>({
    mutationFn: collectFrontierNewsSource,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminFrontierNewsRoot });
      await queryClient.invalidateQueries({ queryKey: queryKeys.moderationRoot });
    },
  });
}

/**
 * Provides cached frontier materials for a status-filtered admin view.
 *
 * @param params - Reactive status and limit values used for query key and request.
 * @returns Vue Query result containing material rows.
 */
export function useFrontierNewsItems(params: MaybeRefOrGetter<FrontierNewsItemsParams>) {
  return useQuery<FrontierNewsItemResponse[], Error>({
    queryKey: computed(() => queryKeys.adminFrontierNewsItems(toValue(params))),
    queryFn: () => fetchFrontierNewsItems(toValue(params)),
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 15_000,
  });
}

/**
 * Re-runs AI整理 for a material and invalidates frontier/moderation queues.
 *
 * @returns Mutation accepting the material ID.
 */
export function useEnrichFrontierNewsItem() {
  const queryClient = useQueryClient();
  return useMutation<FrontierNewsItemResponse, Error, string>({
    mutationFn: enrichFrontierNewsItem,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminFrontierNewsRoot });
      await queryClient.invalidateQueries({ queryKey: queryKeys.moderationRoot });
    },
  });
}

/**
 * Sends a material into the existing moderation queue and refreshes caches.
 *
 * @returns Mutation accepting material ID and optional administrator note.
 */
export function useQueueFrontierNewsItem() {
  const queryClient = useQueryClient();
  return useMutation<FrontierNewsItemResponse, Error, { itemId: string; note?: string }>({
    mutationFn: ({ itemId, note }) => queueFrontierNewsItem(itemId, note),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminFrontierNewsRoot });
      await queryClient.invalidateQueries({ queryKey: queryKeys.moderationRoot });
    },
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
