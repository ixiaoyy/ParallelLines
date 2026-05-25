import { apiDelete, apiGet, apiPost } from "@/shared/api/client";

import type { PushSubscriptionRequest, PushSubscriptionState } from "./model";

export function fetchPushSubscriptionState(): Promise<PushSubscriptionState> {
  return apiGet<PushSubscriptionState>("/notifications/push-subscription");
}

export function savePushSubscription(
  payload: PushSubscriptionRequest,
): Promise<PushSubscriptionState> {
  return apiPost<PushSubscriptionState, PushSubscriptionRequest>(
    "/notifications/push-subscription",
    payload,
  );
}

export function deletePushSubscription(): Promise<PushSubscriptionState> {
  return apiDelete<PushSubscriptionState>("/notifications/push-subscription");
}
