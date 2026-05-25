import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  fetchExternalIntegrationEvents,
  fetchExternalIntegrations,
  fetchGitHubIssuePreview,
  retryExternalIntegrationEvent,
  updateExternalIntegration,
} from "./api";
import type {
  ExternalIntegrationEventInfo,
  ExternalIntegrationInfo,
  ExternalIntegrationUpdateRequest,
  GitHubIssuePreview,
} from "./model";

export function useExternalIntegrations() {
  return useQuery<ExternalIntegrationInfo[], Error>({
    queryKey: queryKeys.adminExternalIntegrations,
    queryFn: fetchExternalIntegrations,
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 30_000,
  });
}

export function useUpdateExternalIntegration() {
  const queryClient = useQueryClient();
  return useMutation<
    ExternalIntegrationInfo,
    Error,
    { provider: string; payload: ExternalIntegrationUpdateRequest }
  >({
    mutationFn: ({ provider, payload }) => updateExternalIntegration(provider, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminExternalIntegrations });
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminRoot });
    },
  });
}

export function useExternalIntegrationEvents() {
  return useQuery<ExternalIntegrationEventInfo[], Error>({
    queryKey: queryKeys.adminExternalIntegrationEvents,
    queryFn: fetchExternalIntegrationEvents,
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 15_000,
  });
}

export function useRetryExternalIntegrationEvent() {
  const queryClient = useQueryClient();
  return useMutation<ExternalIntegrationEventInfo, Error, string>({
    mutationFn: retryExternalIntegrationEvent,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.adminExternalIntegrationEvents });
    },
  });
}

export function useGitHubIssuePreview(url: MaybeRefOrGetter<string>) {
  return useQuery<GitHubIssuePreview, Error>({
    queryKey: computed(() => queryKeys.githubIssuePreview(toValue(url))),
    queryFn: () => fetchGitHubIssuePreview(toValue(url)),
    enabled: computed(() => Boolean(toValue(url).trim())),
    retry: false,
    staleTime: 60_000,
  });
}
