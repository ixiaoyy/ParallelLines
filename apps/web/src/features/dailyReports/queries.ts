import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  acceptDailyReportPreference,
  clearDailyReportHistory,
  confirmDailyReportSession,
  continueDailyReportSession,
  deleteDailyReport,
  fetchDailyReportProfile,
  fetchDailyReports,
  fetchDailyReportSession,
  resetDailyReportProfile,
  startDailyReportSession,
  updateDailyReportProfile,
} from "./api";
import type {
  DailyReportConfirmRequest,
  DailyReportFollowupRequest,
  DailyReportInput,
  DailyReportPreferenceAcceptRequest,
  DailyReportProfile,
  DailyReportProfileUpdateRequest,
  DailyReportRecord,
  DailyReportSession,
} from "./model";

export function useDailyReportProfile() {
  return useQuery<DailyReportProfile, Error>({
    queryKey: queryKeys.dailyReportProfile,
    queryFn: fetchDailyReportProfile,
    enabled: hasAccessToken(),
    staleTime: 30_000,
  });
}

export function useDailyReportHistory(limit = 30) {
  return useQuery<DailyReportRecord[], Error>({
    queryKey: queryKeys.dailyReportHistory(limit),
    queryFn: () => fetchDailyReports(limit),
    enabled: hasAccessToken(),
    staleTime: 10_000,
  });
}

export function useDailyReportSession(sessionId: MaybeRefOrGetter<string>) {
  return useQuery<DailyReportSession, Error>({
    queryKey: computed(() => queryKeys.dailyReportSession(toValue(sessionId))),
    queryFn: () => fetchDailyReportSession(toValue(sessionId)),
    enabled: computed(() => hasAccessToken() && Boolean(toValue(sessionId))),
    staleTime: 5_000,
  });
}

export function useUpdateDailyReportProfile() {
  const queryClient = useQueryClient();
  return useMutation<DailyReportProfile, Error, DailyReportProfileUpdateRequest>({
    mutationFn: updateDailyReportProfile,
    onSuccess: (profile) => {
      queryClient.setQueryData(queryKeys.dailyReportProfile, profile);
    },
  });
}

export function useResetDailyReportProfile() {
  const queryClient = useQueryClient();
  return useMutation<DailyReportProfile, Error, void>({
    mutationFn: resetDailyReportProfile,
    onSuccess: (profile) => {
      queryClient.setQueryData(queryKeys.dailyReportProfile, profile);
    },
  });
}

export function useAcceptDailyReportPreference() {
  const queryClient = useQueryClient();
  return useMutation<DailyReportProfile, Error, DailyReportPreferenceAcceptRequest>({
    mutationFn: acceptDailyReportPreference,
    onSuccess: (profile) => {
      queryClient.setQueryData(queryKeys.dailyReportProfile, profile);
    },
  });
}

export function useStartDailyReportSession() {
  const queryClient = useQueryClient();
  return useMutation<DailyReportSession, Error, DailyReportInput>({
    mutationFn: startDailyReportSession,
    onSuccess: (session) => {
      queryClient.setQueryData(queryKeys.dailyReportSession(session.id), session);
    },
  });
}

export function useContinueDailyReportSession() {
  const queryClient = useQueryClient();
  return useMutation<
    DailyReportSession,
    Error,
    { sessionId: string; payload: DailyReportFollowupRequest }
  >({
    mutationFn: ({ sessionId, payload }) => continueDailyReportSession(sessionId, payload),
    onSuccess: (session) => {
      queryClient.setQueryData(queryKeys.dailyReportSession(session.id), session);
    },
  });
}

export function useConfirmDailyReportSession() {
  const queryClient = useQueryClient();
  return useMutation<
    DailyReportRecord,
    Error,
    { sessionId: string; payload: DailyReportConfirmRequest }
  >({
    mutationFn: ({ sessionId, payload }) => confirmDailyReportSession(sessionId, payload),
    onSuccess: (_, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.dailyReportsRoot });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.dailyReportSession(variables.sessionId),
      });
    },
  });
}

export function useDeleteDailyReport() {
  const queryClient = useQueryClient();
  return useMutation<boolean, Error, string>({
    mutationFn: deleteDailyReport,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.dailyReportsRoot });
    },
  });
}

export function useClearDailyReportHistory() {
  const queryClient = useQueryClient();
  return useMutation<boolean, Error, void>({
    mutationFn: clearDailyReportHistory,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.dailyReportsRoot });
      void queryClient.removeQueries({ queryKey: ["daily-reports", "session"] });
    },
  });
}
