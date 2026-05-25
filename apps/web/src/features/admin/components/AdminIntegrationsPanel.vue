<script setup lang="ts">
import { computed, reactive, ref } from "vue";

import {
  API_KEY_SCOPE_OPTIONS,
  WEBHOOK_EVENT_OPTIONS,
} from "@/features/admin/model";
import {
  useAdminApiKeys,
  useAdminWebhookDeliveries,
  useAdminWebhooks,
  useCreateAdminApiKey,
  useCreateAdminWebhook,
  useDisableAdminApiKey,
  useDisableAdminWebhook,
} from "@/features/admin/queries";
import { relativeTime } from "@/shared/lib/format";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const apiKeysQuery = useAdminApiKeys();
const webhooksQuery = useAdminWebhooks();
const deliveriesQuery = useAdminWebhookDeliveries();
const createApiKeyMutation = useCreateAdminApiKey();
const disableApiKeyMutation = useDisableAdminApiKey();
const createWebhookMutation = useCreateAdminWebhook();
const disableWebhookMutation = useDisableAdminWebhook();

const apiKeyDraft = reactive({
  name: "",
  scopes: ["read"] as string[],
  note: "",
});
const webhookDraft = reactive({
  name: "",
  url: "",
  events: ["topic.created"] as string[],
  note: "",
});
const revealedApiToken = ref("");
const revealedWebhookSecret = ref("");

const apiKeys = computed(() => apiKeysQuery.data.value ?? []);
const webhooks = computed(() => webhooksQuery.data.value ?? []);
const deliveries = computed(() => deliveriesQuery.data.value ?? []);

function toggleApiScope(scope: string) {
  apiKeyDraft.scopes = toggleValue(apiKeyDraft.scopes, scope);
}

function toggleWebhookEvent(event: string) {
  webhookDraft.events = toggleValue(webhookDraft.events, event);
}

function createApiKey() {
  if (!apiKeyDraft.name.trim()) {
    return;
  }
  revealedApiToken.value = "";
  createApiKeyMutation.mutate(
    {
      name: apiKeyDraft.name.trim(),
      scopes: apiKeyDraft.scopes,
      note: apiKeyDraft.note.trim() || null,
    },
    {
      onSuccess: (response) => {
        revealedApiToken.value = response.token;
        apiKeyDraft.name = "";
        apiKeyDraft.note = "";
      },
    },
  );
}

function createWebhook() {
  if (!webhookDraft.name.trim() || !webhookDraft.url.trim()) {
    return;
  }
  revealedWebhookSecret.value = "";
  createWebhookMutation.mutate(
    {
      name: webhookDraft.name.trim(),
      url: webhookDraft.url.trim(),
      events: webhookDraft.events,
      note: webhookDraft.note.trim() || null,
    },
    {
      onSuccess: (response) => {
        revealedWebhookSecret.value = response.secret;
        webhookDraft.name = "";
        webhookDraft.url = "";
        webhookDraft.note = "";
      },
    },
  );
}

function toggleValue(values: string[], value: string): string[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}
</script>

<template>
  <UiCard class="integrations-panel">
    <div class="section-head">
      <div>
        <span class="panel-kicker">Integrations</span>
        <h2>API Key 与 Webhook</h2>
      </div>
      <small>令牌只显示一次；Webhook 使用 HMAC 签名和后台重试。</small>
    </div>

    <section class="integration-section">
      <h3>创建 API Key</h3>
      <div class="integration-form">
        <label>
          <span>名称</span>
          <input v-model="apiKeyDraft.name" maxlength="120" placeholder="例如：Docs sync" />
        </label>
        <label>
          <span>备注</span>
          <input v-model="apiKeyDraft.note" maxlength="500" placeholder="可选" />
        </label>
      </div>
      <div class="chip-grid" aria-label="API Key scopes">
        <button
          v-for="scope in API_KEY_SCOPE_OPTIONS"
          :key="scope"
          type="button"
          :class="{ active: apiKeyDraft.scopes.includes(scope) }"
          @click="toggleApiScope(scope)"
        >
          {{ scope }}
        </button>
      </div>
      <UiButton :disabled="createApiKeyMutation.isPending.value" @click="createApiKey">
        {{ createApiKeyMutation.isPending.value ? "创建中…" : "创建 API Key" }}
      </UiButton>
      <p v-if="revealedApiToken" class="secret-reveal" role="status">
        新令牌：<code>{{ revealedApiToken }}</code>
      </p>
    </section>

    <section class="integration-section">
      <h3>API Key 列表</h3>
      <div v-if="apiKeys.length" class="resource-list">
        <article v-for="apiKey in apiKeys" :key="apiKey.id">
          <strong>{{ apiKey.name }}</strong>
          <span>{{ apiKey.token_prefix }} · {{ apiKey.scopes.length ? apiKey.scopes.join(", ") : "无 scope" }}</span>
          <small>{{ apiKey.disabled_at ? "已禁用" : "启用中" }} · 创建于 {{ relativeTime(apiKey.created_at) }}</small>
          <UiButton
            tone="subtle"
            :disabled="Boolean(apiKey.disabled_at) || disableApiKeyMutation.isPending.value"
            @click="disableApiKeyMutation.mutate(apiKey.id)"
          >
            禁用
          </UiButton>
        </article>
      </div>
      <p v-else class="panel-state">暂无 API Key。</p>
    </section>

    <section class="integration-section">
      <h3>创建 Webhook</h3>
      <div class="integration-form">
        <label>
          <span>名称</span>
          <input v-model="webhookDraft.name" maxlength="120" placeholder="例如：CRM bridge" />
        </label>
        <label>
          <span>URL</span>
          <input v-model="webhookDraft.url" maxlength="1024" placeholder="https://example.com/webhook" />
        </label>
        <label>
          <span>备注</span>
          <input v-model="webhookDraft.note" maxlength="500" placeholder="可选" />
        </label>
      </div>
      <div class="chip-grid" aria-label="Webhook events">
        <button
          v-for="event in WEBHOOK_EVENT_OPTIONS"
          :key="event"
          type="button"
          :class="{ active: webhookDraft.events.includes(event) }"
          @click="toggleWebhookEvent(event)"
        >
          {{ event }}
        </button>
      </div>
      <UiButton :disabled="createWebhookMutation.isPending.value" @click="createWebhook">
        {{ createWebhookMutation.isPending.value ? "创建中…" : "创建 Webhook" }}
      </UiButton>
      <p v-if="revealedWebhookSecret" class="secret-reveal" role="status">
        签名密钥：<code>{{ revealedWebhookSecret }}</code>
      </p>
    </section>

    <section class="integration-section">
      <h3>Webhook 端点</h3>
      <div v-if="webhooks.length" class="resource-list">
        <article v-for="webhook in webhooks" :key="webhook.id">
          <strong>{{ webhook.name }}</strong>
          <span>{{ webhook.url }}</span>
          <small>{{ webhook.active ? "启用中" : "已禁用" }} · {{ webhook.events.join(", ") || "未订阅事件" }}</small>
          <UiButton
            tone="subtle"
            :disabled="!webhook.active || disableWebhookMutation.isPending.value"
            @click="disableWebhookMutation.mutate(webhook.id)"
          >
            禁用
          </UiButton>
        </article>
      </div>
      <p v-else class="panel-state">暂无 Webhook。</p>
    </section>

    <section class="integration-section">
      <h3>最近投递</h3>
      <div v-if="deliveries.length" class="delivery-list">
        <article v-for="delivery in deliveries" :key="delivery.id">
          <strong>{{ delivery.event_type }} · {{ delivery.status }}</strong>
          <span>{{ delivery.endpoint_name ?? delivery.endpoint_id }} · {{ delivery.attempt_count }}/{{ delivery.max_attempts }}</span>
          <small>{{ delivery.last_error || delivery.last_status_code || relativeTime(delivery.created_at) }}</small>
        </article>
      </div>
      <p v-else class="panel-state">暂无投递记录。</p>
    </section>
  </UiCard>
</template>

<style scoped lang="scss" src="./AdminIntegrationsPanel.scss"></style>
