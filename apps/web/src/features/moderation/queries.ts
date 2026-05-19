import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  createFlag,
  fetchAuditLogs,
  fetchModerationQueue,
  setContentHidden,
  updateFlagStatus,
  updateUserStatus,
} from "./api";
import type {
  FlagCreateRequest,
  FlagResponse,
  FlagStatus,
  FlagStatusUpdateRequest,
  FlagTargetType,
  ModerationActionResponse,
  UserStatusResponse,
  UserStatusUpdateRequest,
} from "./model";

export function useCreateFlag() {
  return useMutation<FlagResponse, Error, FlagCreateRequest>({
    mutationFn: (payload) => {
      if (!hasAccessToken()) {
        throw new Error("authentication_required");
      }
      return createFlag(payload);
    },
  });
}

export function useModerationQueue(status: MaybeRefOrGetter<FlagStatus | undefined>) {
  return useQuery({
    queryKey: computed(() => queryKeys.moderationQueue(toValue(status) ?? "all")),
    queryFn: () => fetchModerationQueue(toValue(status)),
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 15_000,
  });
}

export function useAuditLogs() {
  return useQuery({
    queryKey: queryKeys.moderationAudit,
    queryFn: () => fetchAuditLogs(),
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 15_000,
  });
}

export function useFlagStatusMutation() {
  const queryClient = useQueryClient();
  return useMutation<FlagResponse, Error, { flagId: string; payload: FlagStatusUpdateRequest }>({
    mutationFn: ({ flagId, payload }) => updateFlagStatus(flagId, payload),
    onSuccess: () => invalidateModeration(queryClient),
  });
}

export function useContentModerationMutation() {
  const queryClient = useQueryClient();
  return useMutation<
    ModerationActionResponse,
    Error,
    { targetType: FlagTargetType; targetId: string; hidden: boolean; note?: string }
  >({
    mutationFn: ({ targetType, targetId, hidden, note }) =>
      setContentHidden(targetType, targetId, hidden, { note: note ?? null }),
    onSuccess: () => invalidateModeration(queryClient),
  });
}

export function useUserStatusMutation() {
  const queryClient = useQueryClient();
  return useMutation<UserStatusResponse, Error, { userId: string; payload: UserStatusUpdateRequest }>({
    mutationFn: ({ userId, payload }) => updateUserStatus(userId, payload),
    onSuccess: () => invalidateModeration(queryClient),
  });
}

function invalidateModeration(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.moderationRoot });
  void queryClient.invalidateQueries({ queryKey: queryKeys.topics("feed:latest") });
}
