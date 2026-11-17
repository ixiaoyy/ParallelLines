import { computed, toValue, type MaybeRefOrGetter } from "vue";
import { useMutation, useQuery } from "@tanstack/vue-query";

import { queryClient } from "@/shared/api/queryClient";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  createSpaceJournal,
  createSpaceLedgerEntry,
  deleteSpaceJournal,
  deleteSpaceLedgerEntry,
  fetchMySpaceWorkspace,
  fetchPublicSpaceFeed,
  fetchPublicUserSpace,
  likeSpaceJournal,
  reactSpaceJournal,
  syncLocalSpaceToCloud,
  updateMySpaceSettings,
  updateSpaceJournal,
} from "./api";
import type {
  SpaceJournalCreatePayload,
  SpaceJournalItem,
  SpaceJournalUpdatePayload,
  SpaceLedgerCreatePayload,
  SpaceMyWorkspace,
  SpacePublicProfile,
  SpaceReactionKind,
  SpaceSetting,
} from "./model";

export function useMySpaceWorkspace(
  month: MaybeRefOrGetter<string>,
  authScope: MaybeRefOrGetter<string> = "default",
) {
  const monthKey = computed(() => toValue(month));
  const scopeKey = computed(() => toValue(authScope));
  return useQuery({
    queryKey: computed(() => [...queryKeys.spaceWorkspace(monthKey.value), scopeKey.value]),
    queryFn: () => fetchMySpaceWorkspace(monthKey.value),
    staleTime: 30_000,
  });
}

export function usePublicSpaceFeed(limit = 30, enabled: MaybeRefOrGetter<boolean> = true) {
  return useQuery({
    queryKey: queryKeys.spacePublicFeed(limit),
    queryFn: () => fetchPublicSpaceFeed(limit),
    enabled: computed(() => toValue(enabled)),
    staleTime: 30_000,
  });
}

export function usePublicUserSpace(
  identifier: MaybeRefOrGetter<string>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  const resolvedId = computed(() => toValue(identifier).trim());
  return useQuery({
    queryKey: computed(() => queryKeys.spaceUserPublic(resolvedId.value)),
    queryFn: () => fetchPublicUserSpace(resolvedId.value),
    enabled: computed(() => Boolean(resolvedId.value) && toValue(enabled)),
    staleTime: 30_000,
  });
}

function patchCachedJournal(updated: SpaceJournalItem) {
  queryClient.setQueriesData<SpaceMyWorkspace>(
    { queryKey: ["space", "me"] },
    (old) => {
      if (!old) return old;
      const exists = old.journals.some((j) => j.id === updated.id);
      if (!exists) return old;
      return {
        ...old,
        journals: old.journals.map((j) => (j.id === updated.id ? updated : j)),
      };
    },
  );
  queryClient.setQueriesData<SpaceJournalItem[]>(
    { queryKey: ["space", "feed"] },
    (old) => {
      if (!old) return old;
      return old.map((j) => (j.id === updated.id ? updated : j));
    },
  );
  queryClient.setQueriesData<SpacePublicProfile>(
    { queryKey: ["space", "user"] },
    (old) => {
      if (!old) return old;
      const exists = old.journals.some((j) => j.id === updated.id);
      if (!exists) return old;
      return {
        ...old,
        journals: old.journals.map((j) => (j.id === updated.id ? updated : j)),
      };
    },
  );
}

export function useUpdateSpaceSettings() {
  return useMutation({
    mutationFn: (payload: Omit<SpaceSetting, "user_id">) => updateMySpaceSettings(payload),
    onSuccess: (updated) => {
      queryClient.setQueriesData<SpaceMyWorkspace>(
        { queryKey: ["space", "me"] },
        (old) => {
          if (!old) return old;
          return {
            ...old,
            settings: updated,
            ledger_summary: {
              ...old.ledger_summary,
              monthly_budget_cents: updated.monthly_budget_cents,
            },
          };
        },
      );
      void queryClient.invalidateQueries({ queryKey: ["space", "user"] });
    },
  });
}

export function useCreateSpaceJournal() {
  return useMutation({
    mutationFn: (payload: SpaceJournalCreatePayload) => createSpaceJournal(payload),
    onSuccess: (_created, payload) => {
      void queryClient.invalidateQueries({ queryKey: ["space", "me"] });
      if (payload.visibility === "public") {
        void queryClient.invalidateQueries({ queryKey: ["space", "feed"] });
        void queryClient.invalidateQueries({ queryKey: ["space", "user"] });
      }
    },
  });
}

export function useUpdateSpaceJournal() {
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SpaceJournalUpdatePayload }) =>
      updateSpaceJournal(id, payload),
    onSuccess: (updated, { payload }) => {
      if (payload.is_pinned !== undefined || payload.entry_date !== undefined) {
        // 置顶或日期编辑改变排序位置，刷新工作区列表。
        void queryClient.invalidateQueries({ queryKey: ["space", "me"] });
      } else {
        patchCachedJournal(updated);
      }
      if (payload.visibility !== undefined || payload.is_pinned !== undefined) {
        void queryClient.invalidateQueries({ queryKey: ["space", "feed"] });
        void queryClient.invalidateQueries({ queryKey: ["space", "user"] });
      }
    },
  });
}

export function useDeleteSpaceJournal() {
  return useMutation({
    mutationFn: (entryId: string) => deleteSpaceJournal(entryId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.spaceRoot });
    },
  });
}

export function useLikeSpaceJournal() {
  return useMutation({
    mutationFn: (entryId: string) => likeSpaceJournal(entryId),
    onSuccess: (updated) => {
      patchCachedJournal(updated);
    },
  });
}

export function useReactSpaceJournal() {
  return useMutation({
    mutationFn: ({ entryId, kind }: { entryId: string; kind: SpaceReactionKind }) =>
      reactSpaceJournal(entryId, kind),
    onSuccess: (updated) => {
      patchCachedJournal(updated);
    },
  });
}

export function useCreateSpaceLedgerEntry() {
  return useMutation({
    mutationFn: (payload: SpaceLedgerCreatePayload) => createSpaceLedgerEntry(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["space", "me"] });
    },
  });
}

export function useDeleteSpaceLedgerEntry() {
  return useMutation({
    mutationFn: (entryId: string) => deleteSpaceLedgerEntry(entryId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["space", "me"] });
    },
  });
}

export function useSyncLocalSpaceToCloud() {
  return useMutation({
    mutationFn: () => syncLocalSpaceToCloud(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.spaceRoot });
    },
  });
}
