import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import type { TopicCardVM } from "@/entities/topic/model";
import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";
import {
  getRelatedTopics,
  getTopicById,
  getTopicsByBoardSlug,
  topics as mockTopics,
} from "@/shared/api/mockForum";

import { createTopic, fetchBoardTopics, fetchTopic, fetchTopics, searchTopics } from "./api";
import type { TopicSearchParams } from "./api";
import { toTopicCard } from "./model";
import type { CreateTopicRequest, TopicResponse, TopicSort } from "./model";

export function useTopicFeed(sort: MaybeRefOrGetter<TopicSort> = "latest") {
  return useQuery({
    queryKey: computed(() => queryKeys.topics(`feed:${toValue(sort)}`)),
    queryFn: async () => {
      const topicSort = toValue(sort);
      try {
        const topics = await fetchTopics(topicSort);
        return topics.length ? topics.map(toTopicCard) : sortTopicCards(mockTopics, topicSort);
      } catch {
        return sortTopicCards(mockTopics, topicSort);
      }
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
      try {
        const topics = await fetchBoardTopics(slug, topicSort);
        return topics.length ? topics.map(toTopicCard) : sortTopicCards(getTopicsByBoardSlug(slug), topicSort);
      } catch {
        return sortTopicCards(getTopicsByBoardSlug(slug), topicSort);
      }
    },
    enabled: computed(() => Boolean(toValue(boardSlug))),
    staleTime: 20_000,
  });
}

export function useTopicDetail(topicId: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => queryKeys.topic(toValue(topicId))),
    queryFn: async () => {
      const id = toValue(topicId);
      try {
        return toTopicCard(await fetchTopic(id));
      } catch {
        return getTopicById(id) ?? null;
      }
    },
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

      try {
        const topics = await searchTopics(value);
        return topics.map(toTopicCard);
      } catch {
        return searchMockTopics(value);
      }
    },
    enabled: computed(() => Boolean(toValue(params).q.trim())),
    staleTime: 20_000,
  });
}

export function useRelatedTopics(topic: MaybeRefOrGetter<TopicCardVM | null | undefined>) {
  return computed(() => {
    const current = toValue(topic);
    if (!current) {
      return [];
    }

    return getRelatedTopics(current);
  });
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
    },
  });
}

function sortTopicCards(topics: TopicCardVM[], sort: TopicSort): TopicCardVM[] {
  const sorted = [...topics];

  if (sort === "hot") {
    return sorted.sort((left, right) => right.hotScore - left.hotScore);
  }

  if (sort === "top") {
    return sorted.sort((left, right) => right.likeCount + right.replyCount - (left.likeCount + left.replyCount));
  }

  return sorted.sort((left, right) => Date.parse(right.lastPostedAt) - Date.parse(left.lastPostedAt));
}

function searchMockTopics(params: TopicSearchParams): TopicCardVM[] {
  const keyword = params.q.trim().toLocaleLowerCase();
  const filtered = mockTopics.filter((topic) => {
    const matchesKeyword = `${topic.title} ${topic.excerpt} ${topic.tags.join(" ")}`
      .toLocaleLowerCase()
      .includes(keyword);
    const matchesBoard = params.board ? topic.boardSlug === params.board : true;
    const matchesTag = params.tag ? topic.tags.includes(params.tag) : true;
    const matchesAuthor = params.author ? topic.authorName === params.author : true;

    return matchesKeyword && matchesBoard && matchesTag && matchesAuthor;
  });

  return sortTopicCards(filtered, params.sort ?? "latest");
}
