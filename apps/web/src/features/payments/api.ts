import { apiGet } from "@/shared/api/client";

import type { PaymentEvent, SubscriptionPlan, UserSubscription } from "./model";

export function fetchSubscriptionPlans(): Promise<SubscriptionPlan[]> {
  return apiGet<SubscriptionPlan[]>("/subscriptions/plans");
}

export function fetchMySubscription(): Promise<UserSubscription> {
  return apiGet<UserSubscription>("/subscriptions/me");
}

export function fetchAdminPaymentEvents(): Promise<PaymentEvent[]> {
  return apiGet<PaymentEvent[]>("/admin/payments/events");
}
