import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import { fetchModerationAdvice, fetchSimilarTopics, fetchTopicAiSummary, refreshTopicAiSummary } from "./api";
import type {
  ModerationAdvice,
  ModerationAdviceRequest,
  SimilarTopic,
  SimilarTopicsRequest,
  TopicAiSummary,
} from "./model";

export function useTopicAiSummary(topicId: MaybeRefOrGetter<string>) {
  return useQuery<TopicAiSummary | null, Error>({
    queryKey: computed(() => queryKeys.topicAiSummary(toValue(topicId))),
    queryFn: async () => {
      const id = toValue(topicId);
      return id ? fetchTopicAiSummary(id) : null;
    },
    enabled: computed(() => Boolean(toValue(topicId))),
    retry: false,
    staleTime: 120_000,
  });
}

export function useRefreshTopicAiSummary(topicId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();
  return useMutation<TopicAiSummary, Error, void>({
    mutationFn: () => refreshTopicAiSummary(toValue(topicId)),
    onSuccess: async (summary) => {
      queryClient.setQueryData(queryKeys.topicAiSummary(summary.topic_id), summary);
      await queryClient.invalidateQueries({ queryKey: queryKeys.topicAiSummary(summary.topic_id) });
    },
  });
}

export function useSimilarTopics() {
  return useMutation<SimilarTopic[], Error, SimilarTopicsRequest>({
    mutationFn: fetchSimilarTopics,
  });
}

export function useModerationAdvice() {
  return useMutation<ModerationAdvice, Error, ModerationAdviceRequest>({
    mutationFn: (payload) => {
      if (!hasAccessToken()) {
        throw new Error("authentication_required");
      }
      return fetchModerationAdvice(payload);
    },
  });
}
