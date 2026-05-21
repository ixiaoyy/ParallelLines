<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { useCurrentUser } from "@/features/auth/queries";
import { digestLabel, emailToggleItems } from "@/features/email-preferences/model";
import type { DigestFrequency, EmailPreferenceResponse } from "@/features/email-preferences/model";
import {
  useEmailPreferences,
  useUpdateEmailPreferences,
} from "@/features/email-preferences/queries";
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

const currentUser = computed(() => currentUserQuery.data.value);
const preferences = computed(() => preferencesQuery.data.value);
const isBusy = computed(() => updateMutation.isPending.value || preferencesQuery.isPending.value);
const enabledToggleCount = computed(() => {
  if (!draft.value) {
    return 0;
  }

  return emailToggleItems.filter((item) => draft.value?.[item.key]).length;
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
