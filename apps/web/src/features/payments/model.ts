import type { components } from "@/shared/api/generated";

export type SubscriptionPlan = components["schemas"]["SubscriptionPlanResponse"];
export type UserSubscription = components["schemas"]["UserSubscriptionResponse"];
export type PaymentEvent = components["schemas"]["PaymentEventResponse"];

export function formatPrice(plan: SubscriptionPlan): string {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: plan.currency,
  }).format(plan.price_cents / 100);
}

export function subscriptionStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    none: "未订阅",
    active: "生效中",
    past_due: "支付失败",
    canceled: "已取消",
    expired: "已过期",
  };
  return labels[status] ?? status;
}
