import { useQuery } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import type { BoardSummary } from "@/entities/board/model";
import { toTopicCard } from "@/features/topics/model";
import type { TopicCardVM } from "@/entities/topic/model";
import { queryKeys } from "@/shared/api/queryKeys";
import { boards as mockBoards, getBoardBySlug, getTopicsByBoardSlug } from "@/shared/api/mockForum";

import { fetchBoardDetail, fetchBoards } from "./api";
import { toBoardSummary } from "./model";

export interface BoardDetailVM extends BoardSummary {
  latestTopics: TopicCardVM[];
}

export function useBoards() {
  return useQuery({
    queryKey: queryKeys.boards,
    queryFn: async () => {
      try {
        const boards = await fetchBoards();
        return boards.length ? boards.map(toBoardSummary) : mockBoards;
      } catch {
        return mockBoards;
      }
    },
    staleTime: 30_000,
  });
}

export function useBoardDetail(slug: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => queryKeys.board(toValue(slug))),
    queryFn: async () => {
      const boardSlug = toValue(slug);
      try {
        const board = await fetchBoardDetail(boardSlug);
        const latestTopics = board.latest_topics.map(toTopicCard);
        return {
          ...toBoardSummary(board),
          latestTopics: latestTopics.length ? latestTopics : getTopicsByBoardSlug(board.slug),
        } satisfies BoardDetailVM;
      } catch {
        const board = getBoardBySlug(boardSlug);
        if (!board) {
          return null;
        }

        return {
          ...board,
          latestTopics: getTopicsByBoardSlug(board.slug),
        } satisfies BoardDetailVM;
      }
    },
    enabled: computed(() => Boolean(toValue(slug))),
    staleTime: 30_000,
  });
}
