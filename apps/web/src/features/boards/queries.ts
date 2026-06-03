import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import type { BoardSummary } from "@/entities/board/model";
import type { TopicCardVM } from "@/entities/topic/model";
import { toTopicCard } from "@/features/topics/model";
import { TAXONOMY_QUERY_GC_TIME_MS, TAXONOMY_QUERY_STALE_TIME_MS } from "@/shared/api/queryClient";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  createBoard,
  fetchBoardDetail,
  fetchBoardSettings,
  fetchBoards,
  removeBoardMember,
  updateBoardMember,
  updateBoardSettings,
} from "./api";
import type { CreateBoardRequest } from "./api";
import { toBoardSummary } from "./model";
import type {
  BoardMemberRemoveResponse,
  BoardMemberResponse,
  BoardMemberUpdateRequest,
  BoardSettingsResponse,
  BoardSettingsUpdateRequest,
} from "./model";

export interface BoardDetailVM extends BoardSummary {
  latestTopics: TopicCardVM[];
  childBoards: BoardSummary[];
}

// Fetches public board taxonomy for visible navigation/filter surfaces.
// Key parameter: `enabled` gates non-critical hidden consumers; return value is the Vue Query board list state.
export function useBoards(enabled: MaybeRefOrGetter<boolean> = true) {
  return useQuery({
    queryKey: queryKeys.boards,
    queryFn: async () => (await fetchBoards()).map(toBoardSummary),
    enabled: computed(() => Boolean(toValue(enabled))),
    staleTime: TAXONOMY_QUERY_STALE_TIME_MS,
    gcTime: TAXONOMY_QUERY_GC_TIME_MS,
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
        childBoards: board.child_boards.map(toBoardSummary),
      } satisfies BoardDetailVM;
    },
    enabled: computed(() => Boolean(toValue(slug))),
    staleTime: TAXONOMY_QUERY_STALE_TIME_MS,
    gcTime: TAXONOMY_QUERY_GC_TIME_MS,
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

export function useBoardSettings(
  slug: MaybeRefOrGetter<string>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery<BoardSettingsResponse | null, Error>({
    queryKey: computed(() => queryKeys.boardSettings(toValue(slug))),
    queryFn: async () => {
      const boardSlug = toValue(slug);
      if (!boardSlug || !toValue(enabled)) {
        return null;
      }

      return fetchBoardSettings(boardSlug);
    },
    enabled: computed(() => Boolean(toValue(slug)) && toValue(enabled)),
    retry: false,
    staleTime: TAXONOMY_QUERY_STALE_TIME_MS,
    gcTime: TAXONOMY_QUERY_GC_TIME_MS,
  });
}

export function useUpdateBoardSettings(slug: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();

  return useMutation<BoardSummary, Error, BoardSettingsUpdateRequest>({
    mutationFn: async (payload) => toBoardSummary(await updateBoardSettings(toValue(slug), payload)),
    onSuccess: (board) => {
      void invalidateBoardManagementQueries(queryClient, board.slug);
    },
  });
}

export function useUpdateBoardMember(slug: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();

  return useMutation<
    BoardMemberResponse,
    Error,
    { username: string; payload: BoardMemberUpdateRequest }
  >({
    mutationFn: ({ username, payload }) => updateBoardMember(toValue(slug), username, payload),
    onSuccess: () => {
      void invalidateBoardManagementQueries(queryClient, toValue(slug));
    },
  });
}

export function useRemoveBoardMember(slug: MaybeRefOrGetter<string>) {
  const queryClient = useQueryClient();

  return useMutation<BoardMemberRemoveResponse, Error, string>({
    mutationFn: (username) => removeBoardMember(toValue(slug), username),
    onSuccess: () => {
      void invalidateBoardManagementQueries(queryClient, toValue(slug));
    },
  });
}

async function invalidateBoardManagementQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  slug: string,
) {
  await queryClient.invalidateQueries({ queryKey: queryKeys.boards });
  await queryClient.invalidateQueries({ queryKey: queryKeys.board(slug) });
  await queryClient.invalidateQueries({ queryKey: queryKeys.boardSettings(slug) });
  await queryClient.invalidateQueries({ queryKey: queryKeys.topics(`board:${slug}:latest`) });
  await queryClient.invalidateQueries({ queryKey: queryKeys.topics(`board:${slug}:hot`) });
  await queryClient.invalidateQueries({ queryKey: queryKeys.topics(`board:${slug}:top`) });
}
