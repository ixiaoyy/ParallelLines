<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { useCurrentUser } from "@/features/auth/queries";
import { digestLabel, emailToggleItems } from "@/features/email-preferences/model";
import type { DigestFrequency, EmailPreferenceResponse } from "@/features/email-preferences/model";
import {
  useEmailPreferences,
  useUpdateEmailPreferences,
} from "@/features/email-preferences/queries";
import PushNotificationPanel from "@/features/pwa/components/PushNotificationPanel.vue";
import { ApiError } from "@/shared/api/client";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const currentUserQuery = useCurrentUser();
const preferencesQuery = useEmailPreferences();
const updateMutation = useUpdateEmailPreferences();
const draft = ref<EmailPreferenceResponse | null>(null);
const notice = ref("");
const errorMessage = ref("");
const hourOptions = Array.from({ length: 24 }, (_, hour) => ({
  value: hour,
  label: `${String(hour).padStart(2, "0")}:00 UTC`,
}));

const currentUser = computed(() => currentUserQuery.data.value);
const preferences = computed(() => preferencesQuery.data.value);
const isBusy = computed(() => updateMutation.isPending.value || preferencesQuery.isPending.value);
const enabledToggleCount = computed(() => {
  if (!draft.value) {
    return 0;
  }

  return emailToggleItems.filter((item) => draft.value?.[item.key]).length;
});
const quietHoursEnabled = computed({
  get() {
    return Boolean(
      draft.value &&
        draft.value.quiet_hours_start !== null &&
        draft.value.quiet_hours_end !== null,
    );
  },
  set(enabled: boolean) {
    if (!draft.value) {
      return;
    }

    if (enabled) {
      draft.value.quiet_hours_start ??= 22;
      draft.value.quiet_hours_end ??= 7;
      return;
    }

    draft.value.quiet_hours_start = null;
    draft.value.quiet_hours_end = null;
  },
});
const quietHoursSummary = computed(() => {
  if (!draft.value || !quietHoursEnabled.value) {
    return "未开启免打扰，即时邮件会按事件偏好发送。";
  }

  const start = formatHour(draft.value.quiet_hours_start);
  const end = formatHour(draft.value.quiet_hours_end);
  return `${start} 至 ${end} 期间暂停即时通知邮件。`;
});

watch(
  preferences,
  (value) => {
    draft.value = value ? { ...value } : null;
  },
  { immediate: true },
);

async function savePreferences() {
  if (!draft.value) {
    return;
  }

  notice.value = "";
  errorMessage.value = "";
  try {
    const saved = await updateMutation.mutateAsync({
      email_enabled: draft.value.email_enabled,
      notify_replied: draft.value.notify_replied,
      notify_mentioned: draft.value.notify_mentioned,
      notify_liked: draft.value.notify_liked,
      notify_topic_new_post: draft.value.notify_topic_new_post,
      notify_board_new_topic: draft.value.notify_board_new_topic,
      digest_frequency: normalizeDigest(draft.value.digest_frequency),
      quiet_hours_start: draft.value.quiet_hours_start,
      quiet_hours_end: draft.value.quiet_hours_end,
    });
    draft.value = { ...saved };
    notice.value = "邮件偏好已保存。";
  } catch (error) {
    errorMessage.value = toPreferenceError(error);
  }
}

function normalizeDigest(value: string): DigestFrequency {
  return value === "weekly" || value === "daily" ? value : "off";
}

function formatDate(value: string | null): string {
  if (!value) {
    return "尚未发送";
  }

  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatHour(value: number | null): string {
  if (value === null) {
    return "--:-- UTC";
  }

  return `${String(value).padStart(2, "0")}:00 UTC`;
}

function toPreferenceError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "invalid_token") {
      return "登录已失效，请重新登录后再保存。";
    }

    if (error.code === "validation_error") {
      return "偏好格式不正确，请刷新后重试。";
    }
  }

  return error instanceof Error && error.message ? error.message : "邮件偏好保存失败。";
}
</script>

<template>
  <section class="email-page">
    <header class="email-hero">
      <div>
        <UiBadge tone="blue">邮件雷达</UiBadge>
        <h1>把真正重要的讨论送到收件箱。</h1>
        <p>即时通知、摘要邮件和退信保护共用同一套后台任务系统，不再阻塞发帖和回复。</p>
      </div>
      <div v-if="draft" class="email-orbit" aria-label="邮件偏好状态">
        <strong>{{ draft.email_enabled ? enabledToggleCount : 0 }}</strong>
        <span>开启的即时类型</span>
      </div>
    </header>

    <UiCard v-if="!currentUser" class="email-empty">
      <h2>登录后管理邮件偏好</h2>
      <p>你可以关闭某类提醒、选择摘要频率，或在退信恢复后重新开启邮件。</p>
      <RouterLink :to="{ name: 'auth', query: { redirect: '/email-preferences' } }">前往登录</RouterLink>
    </UiCard>

    <div v-else-if="draft" class="email-grid">
      <UiCard class="email-master-card">
        <div>
          <span class="eyebrow">投递总开关</span>
          <h2>{{ draft.email_enabled ? "邮件投递已开启" : "邮件投递已暂停" }}</h2>
          <p>
            当前状态：{{ draft.delivery_status }}
            <template v-if="draft.disabled_reason"> · {{ draft.disabled_reason }}</template>
          </p>
        </div>
        <label class="switch-row switch-row--large">
          <span>{{ draft.email_enabled ? "接收社区邮件" : "暂停所有社区邮件" }}</span>
          <input v-model="draft.email_enabled" type="checkbox" />
        </label>
      </UiCard>

      <UiCard class="email-panel email-panel--wide">
        <header>
          <div>
            <span class="eyebrow">即时通知</span>
            <h2>选择哪些事件能打断你</h2>
          </div>
          <span class="email-count">{{ enabledToggleCount }}/{{ emailToggleItems.length }}</span>
        </header>
        <div class="toggle-list">
          <label v-for="item in emailToggleItems" :key="item.key" class="toggle-card">
            <input v-model="draft[item.key]" type="checkbox" :disabled="!draft.email_enabled" />
            <span>
              <strong>{{ item.title }}</strong>
              <small>{{ item.description }}</small>
            </span>
            <em>{{ item.badge }}</em>
          </label>
        </div>
      </UiCard>

      <UiCard class="email-panel digest-panel">
        <header>
          <span class="eyebrow">摘要节奏</span>
          <h2>{{ digestLabel(draft.digest_frequency) }}</h2>
          <p>摘要只会发送给活跃账号，并汇总最近未读通知。</p>
        </header>
        <select v-model="draft.digest_frequency" :disabled="!draft.email_enabled">
          <option value="off">关闭摘要</option>
          <option value="daily">每日摘要</option>
          <option value="weekly">每周摘要</option>
        </select>
      </UiCard>

      <UiCard class="email-panel quiet-panel">
        <header>
          <span class="eyebrow">免打扰</span>
          <h2>{{ quietHoursEnabled ? "安静时段已启用" : "安静时段未启用" }}</h2>
          <p>{{ quietHoursSummary }}</p>
        </header>
        <label class="quiet-toggle">
          <span>暂停安静时段内的即时邮件</span>
          <input v-model="quietHoursEnabled" type="checkbox" :disabled="!draft.email_enabled" />
        </label>
        <div class="quiet-range" :aria-disabled="!quietHoursEnabled">
          <label>
            <span>开始</span>
            <select
              v-model.number="draft.quiet_hours_start"
              :disabled="!draft.email_enabled || !quietHoursEnabled"
            >
              <option v-for="option in hourOptions" :key="`start-${option.value}`" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
          <label>
            <span>结束</span>
            <select
              v-model.number="draft.quiet_hours_end"
              :disabled="!draft.email_enabled || !quietHoursEnabled"
            >
              <option v-for="option in hourOptions" :key="`end-${option.value}`" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
        </div>
      </UiCard>

      <PushNotificationPanel />

      <UiCard class="email-panel telemetry-panel">
        <header>
          <span class="eyebrow">投递遥测</span>
          <h2>最后摘要</h2>
          <p>{{ formatDate(draft.last_digest_sent_at) }}</p>
        </header>
        <p class="telemetry-copy">退信或投诉会自动暂停投递，避免继续打扰无效邮箱。</p>
      </UiCard>

      <div class="email-actions">
        <p v-if="notice" class="email-success">{{ notice }}</p>
        <p v-if="errorMessage" class="email-error">{{ errorMessage }}</p>
        <UiButton tone="primary" :disabled="isBusy" @click="savePreferences">保存邮件偏好</UiButton>
      </div>
    </div>

    <UiCard v-else class="email-empty">
      <h2>正在读取邮件偏好…</h2>
      <p>偏好会随账号自动创建。</p>
    </UiCard>
  </section>
</template>

<style scoped lang="scss" src="./EmailPreferencesPage.scss"></style>
