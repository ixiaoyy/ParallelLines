import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import type { BoardSummary } from "@/entities/board/model";
import { toTopicCard } from "@/features/topics/model";
import type { TopicCardVM } from "@/entities/topic/model";
import { queryKeys } from "@/shared/api/queryKeys";

import { createBoard, fetchBoardDetail, fetchBoards } from "./api";
import type { CreateBoardRequest } from "./api";
import { toBoardSummary } from "./model";

export interface BoardDetailVM extends BoardSummary {
  latestTopics: TopicCardVM[];
}

export function useBoards() {
  return useQuery({
    queryKey: queryKeys.boards,
    queryFn: async () => (await fetchBoards()).map(toBoardSummary),
    staleTime: 30_000,
  });
}

export function useBoardDetail(slug: MaybeRefOrGetter<string>) {
  return useQuery({
    queryKey: computed(() => queryKeys.board(toValue(slug))),
    queryFn: async () => {
      const boardSlug = toValue(slug);
      const board = await fetchBoardDetail(boardSlug);
      return {
        ...toBoardSummary(board),
        latestTopics: board.latest_topics.map(toTopicCard),
      } satisfies BoardDetailVM;
    },
    enabled: computed(() => Boolean(toValue(slug))),
    staleTime: 30_000,
  });
}

export function useCreateBoard() {
  const queryClient = useQueryClient();

  return useMutation<BoardSummary, Error, CreateBoardRequest>({
    mutationFn: async (payload) => toBoardSummary(await createBoard(payload)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.boards });
    },
  });
}
