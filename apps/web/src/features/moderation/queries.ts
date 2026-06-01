import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  appealReviewable,
  claimReviewable,
  createFlag,
  decideReviewable,
  fetchAuditLogs,
  fetchModerationQueue,
  fetchMyReviewables,
  fetchReviewables,
  releaseReviewable,
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
  ReviewableAppealRequest,
  ReviewableDecisionRequest,
  ReviewableResponse,
  ReviewableStatus,
  ReviewableType,
  UserStatusResponse,
  UserStatusUpdateRequest,
} from "./model";

const PUBLISH_REVIEWABLE_TYPES: ReviewableType[] = ["queued_topic", "queued_post", "queued_edit"];

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

export function useReviewableQueue(status: MaybeRefOrGetter<ReviewableStatus | "all">) {
  return useQuery({
    queryKey: computed(() => queryKeys.moderationReviewables(toValue(status))),
    queryFn: () => {
      const value = toValue(status);
      return fetchReviewables(value === "all" ? undefined : value);
    },
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 15_000,
  });
}

export function usePublishReviewableQueue(status: MaybeRefOrGetter<ReviewableStatus | "all">) {
  return useQuery({
    queryKey: computed(() => queryKeys.moderationPublishReviewables(toValue(status))),
    queryFn: async () => {
      const value = toValue(status);
      const normalizedStatus = value === "all" ? undefined : value;
      const batches = await Promise.all(
        PUBLISH_REVIEWABLE_TYPES.map((type) => fetchReviewables(normalizedStatus, type)),
      );

      return batches
        .flat()
        .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at));
    },
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 15_000,
  });
}

export function useMyReviewables() {
  return useQuery({
    queryKey: queryKeys.moderationMyReviewables,
    queryFn: () => fetchMyReviewables(),
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

export function useClaimReviewableMutation() {
  const queryClient = useQueryClient();
  return useMutation<ReviewableResponse, Error, string>({
    mutationFn: claimReviewable,
    onSuccess: () => invalidateModeration(queryClient),
  });
}

export function useReleaseReviewableMutation() {
  const queryClient = useQueryClient();
  return useMutation<ReviewableResponse, Error, string>({
    mutationFn: releaseReviewable,
    onSuccess: () => invalidateModeration(queryClient),
  });
}

export function useReviewableDecisionMutation() {
  const queryClient = useQueryClient();
  return useMutation<
    ReviewableResponse,
    Error,
    { reviewableId: string; payload: ReviewableDecisionRequest }
  >({
    mutationFn: ({ reviewableId, payload }) => decideReviewable(reviewableId, payload),
    onSuccess: () => invalidateModeration(queryClient),
  });
}

export function useAppealReviewableMutation() {
  const queryClient = useQueryClient();
  return useMutation<
    ReviewableResponse,
    Error,
    { reviewableId: string; payload: ReviewableAppealRequest }
  >({
    mutationFn: ({ reviewableId, payload }) => appealReviewable(reviewableId, payload),
    onSuccess: () => invalidateModeration(queryClient),
  });
}

function invalidateModeration(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.moderationRoot });
  void queryClient.invalidateQueries({ queryKey: queryKeys.moderationMyReviewables });
  void queryClient.invalidateQueries({ queryKey: queryKeys.topics("feed:latest") });
}
