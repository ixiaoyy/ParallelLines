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
  updateMySpaceSettings,
  updateSpaceJournal,
} from "./api";
import type {
  SpaceJournalCreatePayload,
  SpaceJournalUpdatePayload,
  SpaceLedgerCreatePayload,
  SpaceSetting,
} from "./model";

export function useMySpaceWorkspace(month: MaybeRefOrGetter<string>) {
  const monthKey = computed(() => toValue(month));
  return useQuery({
    queryKey: computed(() => queryKeys.spaceWorkspace(monthKey.value)),
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

export function useUpdateSpaceSettings() {
  return useMutation({
    mutationFn: (payload: Omit<SpaceSetting, "user_id">) => updateMySpaceSettings(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.spaceRoot });
    },
  });
}

export function useCreateSpaceJournal() {
  return useMutation({
    mutationFn: (payload: SpaceJournalCreatePayload) => createSpaceJournal(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.spaceRoot });
    },
  });
}

export function useUpdateSpaceJournal() {
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: SpaceJournalUpdatePayload }) =>
      updateSpaceJournal(id, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.spaceRoot });
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
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.spaceRoot });
    },
  });
}

export function useCreateSpaceLedgerEntry() {
  return useMutation({
    mutationFn: (payload: SpaceLedgerCreatePayload) => createSpaceLedgerEntry(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.spaceRoot });
    },
  });
}

export function useDeleteSpaceLedgerEntry() {
  return useMutation({
    mutationFn: (entryId: string) => deleteSpaceLedgerEntry(entryId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.spaceRoot });
    },
  });
}
