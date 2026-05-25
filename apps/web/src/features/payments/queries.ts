import { useQuery } from "@tanstack/vue-query";
import { computed, toValue } from "vue";
import type { MaybeRefOrGetter } from "vue";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import { fetchAdminPaymentEvents, fetchMySubscription, fetchSubscriptionPlans } from "./api";
import type { PaymentEvent, SubscriptionPlan, UserSubscription } from "./model";

export function useSubscriptionPlans() {
  return useQuery<SubscriptionPlan[], Error>({
    queryKey: queryKeys.subscriptionPlans,
    queryFn: fetchSubscriptionPlans,
    staleTime: 60_000,
  });
}

export function useMySubscription(enabled: MaybeRefOrGetter<boolean> = true) {
  return useQuery<UserSubscription | null, Error>({
    queryKey: queryKeys.mySubscription,
    queryFn: async () => {
      if (!hasAccessToken()) {
        return null;
      }
      return fetchMySubscription();
    },
    enabled: computed(() => toValue(enabled)),
    staleTime: 30_000,
  });
}

export function useAdminPaymentEvents(enabled: MaybeRefOrGetter<boolean> = true) {
  return useQuery<PaymentEvent[], Error>({
    queryKey: queryKeys.adminPaymentEvents,
    queryFn: async () => {
      if (!hasAccessToken()) {
        return [];
      }
      return fetchAdminPaymentEvents();
    },
    enabled: computed(() => toValue(enabled)),
    staleTime: 30_000,
  });
}
