import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import { deleteDraft, lookupDraft, saveDraft } from "./api";
import type { DraftResponse, DraftSaveRequest } from "./model";

export function useDraft(
  targetType: MaybeRefOrGetter<string>,
  targetId: MaybeRefOrGetter<string> = "",
) {
  return useQuery({
    queryKey: computed(() => queryKeys.draft(toValue(targetType), toValue(targetId))),
    queryFn: () => lookupDraft(toValue(targetType), toValue(targetId)),
    enabled: computed(() => hasAccessToken() && Boolean(toValue(targetType))),
    staleTime: 5_000,
  });
}

export function useSaveDraft() {
  const queryClient = useQueryClient();

  return useMutation<DraftResponse, Error, DraftSaveRequest>({
    mutationFn: (payload) => saveDraft(payload),
    onSuccess: (data) => {
      void queryClient.setQueryData(
        queryKeys.draft(data.target_type, data.target_id),
        data,
      );
    },
  });
}

export function useDeleteDraft() {
  const queryClient = useQueryClient();

  return useMutation<boolean, Error, { targetType: string; targetId?: string }>({
    mutationFn: ({ targetType, targetId = "" }) => deleteDraft(targetType, targetId),
    onSuccess: (_, variables) => {
      void queryClient.setQueryData(
        queryKeys.draft(variables.targetType, variables.targetId ?? ""),
        null,
      );
    },
  });
}
