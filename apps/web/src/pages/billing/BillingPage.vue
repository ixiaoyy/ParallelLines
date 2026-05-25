<script setup lang="ts">
import { CrownOutlined, SafetyCertificateOutlined } from "@ant-design/icons-vue";
import { computed } from "vue";

import { useCurrentUser } from "@/features/auth/queries";
import { formatPrice, subscriptionStatusLabel } from "@/features/payments/model";
import { useMySubscription, useSubscriptionPlans } from "@/features/payments/queries";
import { hasAccessToken } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
import UiBadge from "@/shared/ui/Badge.vue";
import UiCard from "@/shared/ui/Card.vue";

const currentUserQuery = useCurrentUser();
const currentUser = computed(() => currentUserQuery.data.value);
const hasStoredToken = hasAccessToken();
const isCheckingSession = computed(() => hasStoredToken && currentUserQuery.isPending.value);
const plansQuery = useSubscriptionPlans();
const subscriptionQuery = useMySubscription(computed(() => Boolean(currentUser.value)));
const plans = computed(() => plansQuery.data.value ?? []);
const subscription = computed(() => subscriptionQuery.data.value);
</script>

<template>
  <div class="billing-page">
    <UiCard class="billing-hero">
      <UiBadge tone="amber">Membership</UiBadge>
      <h1>付费会员与订阅</h1>
      <p>当前先接入 provider-agnostic 的签名 webhook、权益授予和账单事件追踪，为后续真实支付页预留接口。</p>
    </UiCard>

    <UiCard v-if="isCheckingSession" class="billing-state">正在确认登录状态…</UiCard>
    <UiCard v-else-if="!currentUser" class="billing-state">
      <strong>登录后查看会员权益</strong>
      <RouterLink to="/auth?redirect=/billing">前往登录</RouterLink>
    </UiCard>

    <section v-else class="billing-grid">
      <UiCard class="subscription-card">
        <div class="card-heading">
          <CrownOutlined />
          <div>
            <span>当前订阅</span>
            <h2>{{ subscriptionStatusLabel(subscription?.status ?? "none") }}</h2>
          </div>
        </div>
        <p v-if="subscription?.current_period_end">
          当前周期 {{ relativeTime(subscription.current_period_end) }}结束
        </p>
        <p v-else>还没有生效的付费会员订阅。</p>
        <div class="entitlement-list">
          <span v-for="item in subscription?.entitlements ?? []" :key="item">{{ item }}</span>
          <span v-if="!(subscription?.entitlements?.length)">暂无付费权益</span>
        </div>
      </UiCard>

      <UiCard class="webhook-card">
        <div class="card-heading">
          <SafetyCertificateOutlined />
          <div>
            <span>支付安全边界</span>
            <h2>签名 Webhook</h2>
          </div>
        </div>
        <p>支付成功、失败和订阅删除都通过签名 webhook 写入后台事件，避免前端伪造权益。</p>
      </UiCard>
    </section>

    <section class="plan-grid" aria-label="会员计划">
      <UiCard v-for="plan in plans" :key="plan.id" class="plan-card">
        <span class="plan-badge">{{ plan.interval === "year" ? "年付" : "月付" }}</span>
        <h2>{{ plan.name }}</h2>
        <strong>{{ formatPrice(plan) }}</strong>
        <p>{{ plan.description }}</p>
        <div class="entitlement-list">
          <span v-for="item in plan.entitlements" :key="item">{{ item }}</span>
        </div>
      </UiCard>
    </section>
  </div>
</template>

<style scoped lang="scss" src="./BillingPage.scss"></style>
