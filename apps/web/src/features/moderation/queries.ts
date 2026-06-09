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
  decideReviewablesBulk,
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
  ReviewableBulkDecisionRequest,
  ReviewableBulkDecisionResponse,
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

export function useModerationQueue(
  status: MaybeRefOrGetter<FlagStatus | undefined>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery({
    queryKey: computed(() => queryKeys.moderationQueue(toValue(status) ?? "all")),
    queryFn: () => fetchModerationQueue(toValue(status)),
    enabled: computed(() => hasAccessToken() && toValue(enabled)),
    retry: false,
    staleTime: 15_000,
  });
}

export function useAuditLogs(enabled: MaybeRefOrGetter<boolean> = true) {
  return useQuery({
    queryKey: queryKeys.moderationAudit,
    queryFn: () => fetchAuditLogs(),
    enabled: computed(() => hasAccessToken() && toValue(enabled)),
    retry: false,
    staleTime: 15_000,
  });
}

export function useReviewableQueue(
  status: MaybeRefOrGetter<ReviewableStatus | "all">,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery({
    queryKey: computed(() => queryKeys.moderationReviewables(toValue(status))),
    queryFn: () => {
      const value = toValue(status);
      return fetchReviewables(value === "all" ? undefined : value);
    },
    enabled: computed(() => hasAccessToken() && toValue(enabled)),
    retry: false,
    staleTime: 15_000,
  });
}

export function usePublishReviewableQueue(
  status: MaybeRefOrGetter<ReviewableStatus | "all">,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
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
    enabled: computed(() => hasAccessToken() && toValue(enabled)),
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

/**
 * Creates the moderation visibility mutation for hiding or restoring published content.
 *
 * @param options.awaitInvalidation - Set false when a caller must run its own success flow before global cache refreshes finish.
 * @returns TanStack mutation; side effects prune hidden topics and refresh moderation/public content caches.
 */
export function useContentModerationMutation(options: { awaitInvalidation?: boolean } = {}) {
  const queryClient = useQueryClient();
  return useMutation<
    ModerationActionResponse,
    Error,
    { targetType: FlagTargetType; targetId: string; hidden: boolean; note?: string }
  >({
    mutationFn: ({ targetType, targetId, hidden, note }) =>
      setContentHidden(targetType, targetId, hidden, { note: note ?? null }),
    onSuccess: (_response, variables) => {
      if (variables.targetType === "topic" && variables.hidden) {
        pruneTopicFromVisibleCaches(queryClient, variables.targetId);
      }
      const invalidation = invalidateModeration(queryClient);
      return options.awaitInvalidation === false ? undefined : invalidation;
    },
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

/**
 * Creates the bulk reviewable-decision mutation used by touch batch selection.
 *
 * @returns TanStack mutation; side effects apply the backend batch action and refresh moderation/public caches.
 */
export function useReviewableBulkDecisionMutation() {
  const queryClient = useQueryClient();
  return useMutation<ReviewableBulkDecisionResponse, Error, ReviewableBulkDecisionRequest>({
    mutationFn: decideReviewablesBulk,
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

/**
 * Invalidates moderation-related caches and resolves only after active refetches finish.
 *
 * @param queryClient - TanStack Query client that owns the current moderation caches.
 * @returns Promise that keeps the mutation pending while the visible queue and feed refresh.
 */
async function invalidateModeration(queryClient: ReturnType<typeof useQueryClient>) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.moderationRoot }),
    queryClient.invalidateQueries({ queryKey: queryKeys.moderationMyReviewables }),
    queryClient.invalidateQueries({ queryKey: queryKeys.topicsRoot }),
    queryClient.invalidateQueries({ queryKey: queryKeys.boards }),
    queryClient.invalidateQueries({ queryKey: queryKeys.tagsRoot }),
  ]);
}

/**
 * Immediately removes a hidden topic from cached topic-list arrays before the refetch returns.
 *
 * @param queryClient - TanStack Query client that owns visible topic caches.
 * @param topicId - Hidden topic id that should disappear from feed, board, search, and related lists.
 * @returns Nothing; side effects prune topic-list query data and remove stale topic detail/posts caches.
 */
function pruneTopicFromVisibleCaches(
  queryClient: ReturnType<typeof useQueryClient>,
  topicId: string,
) {
  const topicQueries = queryClient.getQueryCache().findAll({ queryKey: queryKeys.topicsRoot });
  topicQueries.forEach((query) => {
    const [, scope] = query.queryKey;
    if (typeof scope !== "string") {
      return;
    }

    queryClient.setQueryData(query.queryKey, (current: unknown) => {
      if (!Array.isArray(current)) {
        return current;
      }
      const next = current.filter((entry) => !isCachedTopicEntry(entry, topicId));
      return next.length === current.length ? current : next;
    });
  });
  queryClient.removeQueries({ queryKey: queryKeys.topic(topicId), exact: true });
  queryClient.removeQueries({ queryKey: queryKeys.posts(topicId) });
}

/**
 * Checks whether an unknown cached list item is the topic row being removed.
 *
 * @param entry - Unknown cache entry from a topic-list query.
 * @param topicId - Topic id to compare against `entry.id`.
 * @returns True when the cache entry is an object with the requested topic id.
 */
function isCachedTopicEntry(entry: unknown, topicId: string): entry is { id: string } {
  return (
    typeof entry === "object" &&
    entry !== null &&
    "id" in entry &&
    (entry as { id?: unknown }).id === topicId
  );
}
