import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import type { TopicCardVM } from "@/entities/topic/model";
import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  createTopic,
  fetchBoardTopics,
  fetchTopic,
  fetchTopics,
  mergeTopic,
  moveTopic,
  searchTopics,
  setTopicSolution,
  splitTopic,
  updateTopicLifecycle,
  votePoll,
} from "./api";
import type { TopicSearchParams } from "./api";
import { toTopicCard } from "./model";
import type {
  CreateTopicRequest,
  PollResponse,
  PollVoteRequest,
  TopicLifecycleRequest,
  TopicLifecycleResponse,
  TopicMergeRequest,
  TopicMoveRequest,
  TopicResponse,
  TopicSolutionRequest,
  TopicSort,
  TopicSplitRequest,
} from "./model";

export function useTopicFeed(sort: MaybeRefOrGetter<TopicSort> = "latest") {
  return useQuery({
    queryKey: computed(() => queryKeys.topics(`feed:${toValue(sort)}`)),
    queryFn: async () => {
      const topicSort = toValue(sort);
      return (await fetchTopics(topicSort)).map(toTopicCard);
    },
    staleTime: 20_000,
  });
}

export function useBoardTopics(
  boardSlug: MaybeRefOrGetter<string>,
  sort: MaybeRefOrGetter<TopicSort> = "latest",
) {
  return useQuery({
    queryKey: computed(() => queryKeys.topics(`board:${toValue(boardSlug)}:${toValue(sort)}`)),
    queryFn: async () => {
      const slug = toValue(boardSlug);
      const topicSort = toValue(sort);
      return (await fetchBoardTopics(slug, topicSort)).map(toTopicCard);
    },
    enabled: computed(() => Boolean(toValue(boardSlug))),
    staleTime: 20_000,
  });
}

export function useTopicDetail(topicId: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => queryKeys.topic(toValue(topicId))),
    queryFn: async () => toTopicCard(await fetchTopic(toValue(topicId))),
    enabled: computed(() => Boolean(toValue(topicId))),
    staleTime: 20_000,
  });
}

export function useTopicSearch(params: MaybeRefOrGetter<TopicSearchParams>) {
  return useQuery({
    queryKey: computed(() => {
      const value = toValue(params);
      return queryKeys.topics(
        `search:${value.q}:${value.board ?? ""}:${value.tag ?? ""}:${value.author ?? ""}:${value.sort ?? "latest"}`,
      );
    }),
    queryFn: async () => {
      const value = toValue(params);
      if (!value.q.trim()) {
        return [];
      }

      return (await searchTopics(value)).map(toTopicCard);
    },
    enabled: computed(() => Boolean(toValue(params).q.trim())),
    staleTime: 20_000,
  });
}

export function useRelatedTopics(topic: MaybeRefOrGetter<TopicCardVM | null | undefined>) {
  const relatedQuery = useQuery({
    queryKey: computed(() => {
      const current = toValue(topic);
      return queryKeys.topics(`related:${current?.boardSlug ?? ""}:${current?.id ?? ""}`);
    }),
    queryFn: async () => {
      const current = toValue(topic);
      if (!current) {
        return [];
      }

      const topics = await fetchBoardTopics(current.boardSlug, "latest", 4);
      return topics
        .map(toTopicCard)
        .filter((candidate) => candidate.id !== current.id)
        .slice(0, 3);
    },
    enabled: computed(() => Boolean(toValue(topic)?.boardSlug)),
    staleTime: 30_000,
  });

  return computed(() => relatedQuery.data.value ?? []);
}

export function useCreateTopic() {
  const queryClient = useQueryClient();

  return useMutation<TopicResponse, Error, { boardSlug: string; payload: CreateTopicRequest }>({
    mutationFn: ({ boardSlug, payload }) => {
      if (!hasAccessToken()) {
        throw new Error("authentication_required");
      }

      return createTopic(boardSlug, payload);
    },
    onSuccess: (_topic, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.boards });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.topics(`board:${variables.boardSlug}:latest`),
      });
      void queryClient.invalidateQueries({ queryKey: queryKeys.topics("feed:latest") });
  void queryClient.invalidateQueries({ queryKey: queryKeys.topics("feed:votes") });
    },
  });
}


export function useSetTopicSolution(topicId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();

  return useMutation<TopicResponse, Error, TopicSolutionRequest>({
    mutationFn: (payload) => {
      const id = toValue(topicId);
      if (!id || !hasAccessToken()) {
        throw new Error("authentication_required");
      }

      return setTopicSolution(id, payload);
    },
    onSuccess: (topic) => {
      invalidateTopicLifecycleQueries(queryClient, topic.id, topic.board_slug);
      void queryClient.invalidateQueries({ queryKey: queryKeys.topics("feed:votes") });
    },
  });
}

export function useVotePoll(topicId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();

  return useMutation<PollResponse, Error, PollVoteRequest>({
    mutationFn: (payload) => {
      const id = toValue(topicId);
      if (!id || !hasAccessToken()) {
        throw new Error("authentication_required");
      }

      return votePoll(id, payload);
    },
    onSuccess: () => {
      const id = toValue(topicId);
      void queryClient.invalidateQueries({ queryKey: queryKeys.topic(id) });
    },
  });
}

export function useTopicLifecycle(topicId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();

  return useMutation<TopicResponse, Error, TopicLifecycleRequest>({
    mutationFn: (payload) => {
      const id = toValue(topicId);
      if (!id || !hasAccessToken()) {
        throw new Error("authentication_required");
      }

      return updateTopicLifecycle(id, payload);
    },
    onSuccess: (topic) => {
      invalidateTopicLifecycleQueries(queryClient, topic.id, topic.board_slug);
    },
  });
}

export function useMoveTopic(topicId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();

  return useMutation<TopicResponse, Error, TopicMoveRequest>({
    mutationFn: (payload) => {
      const id = toValue(topicId);
      if (!id || !hasAccessToken()) {
        throw new Error("authentication_required");
      }

      return moveTopic(id, payload);
    },
    onSuccess: (topic) => {
      invalidateTopicLifecycleQueries(queryClient, topic.id, topic.board_slug);
      void queryClient.invalidateQueries({ queryKey: queryKeys.boards });
    },
  });
}

export function useSplitTopic(topicId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();

  return useMutation<TopicLifecycleResponse, Error, TopicSplitRequest>({
    mutationFn: (payload) => {
      const id = toValue(topicId);
      if (!id || !hasAccessToken()) {
        throw new Error("authentication_required");
      }

      return splitTopic(id, payload);
    },
    onSuccess: (response) => {
      if (response.source_topic) {
        invalidateTopicLifecycleQueries(
          queryClient,
          response.source_topic.id,
          response.source_topic.board_slug,
        );
      }
      invalidateTopicLifecycleQueries(
        queryClient,
        response.target_topic.id,
        response.target_topic.board_slug,
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.boards });
    },
  });
}

export function useMergeTopic(topicId: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();

  return useMutation<TopicLifecycleResponse, Error, TopicMergeRequest>({
    mutationFn: (payload) => {
      const id = toValue(topicId);
      if (!id || !hasAccessToken()) {
        throw new Error("authentication_required");
      }

      return mergeTopic(id, payload);
    },
    onSuccess: (response) => {
      const sourceId = toValue(topicId);
      void queryClient.invalidateQueries({ queryKey: queryKeys.topic(sourceId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.posts(sourceId) });
      invalidateTopicLifecycleQueries(
        queryClient,
        response.target_topic.id,
        response.target_topic.board_slug,
      );
      void queryClient.invalidateQueries({ queryKey: queryKeys.boards });
    },
  });
}

function invalidateTopicLifecycleQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  topicId: string,
  boardSlug: string,
) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.topic(topicId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.posts(topicId) });
  void queryClient.invalidateQueries({ queryKey: queryKeys.topics("feed:latest") });
  void queryClient.invalidateQueries({ queryKey: queryKeys.topics("feed:votes") });
  void queryClient.invalidateQueries({ queryKey: queryKeys.topics(`board:${boardSlug}:latest`) });
}
