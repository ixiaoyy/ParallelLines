import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";
import { computed } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import { deletePushSubscription, fetchPushSubscriptionState, savePushSubscription } from "./api";
import type { PushSubscriptionRequest, PushSubscriptionState } from "./model";

export function usePushSubscriptionState() {
  return useQuery<PushSubscriptionState, Error>({
    queryKey: queryKeys.pushSubscription,
    queryFn: fetchPushSubscriptionState,
    enabled: computed(() => hasAccessToken()),
    retry: false,
    staleTime: 60_000,
  });
}

export function useSavePushSubscription() {
  const queryClient = useQueryClient();
  return useMutation<PushSubscriptionState, Error, PushSubscriptionRequest>({
    mutationFn: savePushSubscription,
    onSuccess: async (state) => {
      queryClient.setQueryData(queryKeys.pushSubscription, state);
      await queryClient.invalidateQueries({ queryKey: queryKeys.pushSubscription });
    },
  });
}

export function useDeletePushSubscription() {
  const queryClient = useQueryClient();
  return useMutation<PushSubscriptionState, Error, void>({
    mutationFn: deletePushSubscription,
    onSuccess: async (state) => {
      queryClient.setQueryData(queryKeys.pushSubscription, state);
      await queryClient.invalidateQueries({ queryKey: queryKeys.pushSubscription });
    },
  });
}
