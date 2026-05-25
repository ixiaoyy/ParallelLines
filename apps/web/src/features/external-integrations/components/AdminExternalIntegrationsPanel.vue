<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import {
  integrationStatusLabel,
  providerLabel,
} from "@/features/external-integrations/model";
import {
  useExternalIntegrationEvents,
  useExternalIntegrations,
  useGitHubIssuePreview,
  useRetryExternalIntegrationEvent,
  useUpdateExternalIntegration,
} from "@/features/external-integrations/queries";
import { relativeTime } from "@/shared/lib/format";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const integrationsQuery = useExternalIntegrations();
const eventsQuery = useExternalIntegrationEvents();
const updateIntegration = useUpdateExternalIntegration();
const retryEvent = useRetryExternalIntegrationEvent();
const issueUrl = ref("https://github.com/acme/app/issues/42");
const issuePreviewQuery = useGitHubIssuePreview(computed(() => issueUrl.value.trim()));

const enabledDrafts = reactive<Record<string, boolean>>({});
const configDrafts = reactive<Record<string, Record<string, string>>>({});
const integrations = computed(() => integrationsQuery.data.value ?? []);
const events = computed(() => eventsQuery.data.value ?? []);

watch(
  integrations,
  (items) => {
    for (const item of items) {
      enabledDrafts[item.provider] = item.enabled;
      configDrafts[item.provider] = configDrafts[item.provider] ?? {};
      for (const key of [...item.required_config, ...optionalConfigKeys(item.provider)]) {
        const value = item.config[key];
        configDrafts[item.provider][key] = typeof value === "string" ? value : "";
      }
    }
  },
  { immediate: true },
);

function optionalConfigKeys(provider: string): string[] {
  if (provider === "github") {
    return ["repository_url"];
  }
  if (provider === "zendesk") {
    return ["email"];
  }
  return [];
}

function saveProvider(provider: string) {
  updateIntegration.mutate({
    provider,
    payload: {
      enabled: Boolean(enabledDrafts[provider]),
      config: configDrafts[provider] ?? {},
    },
  });
}
</script>

<template>
  <UiCard class="external-integrations-panel">
    <div class="section-head">
      <div>
        <span class="panel-kicker">External providers</span>
        <h2>GitHub / Zendesk / Patreon 集成</h2>
      </div>
      <small>Provider 配置会做后台健康检查；GitHub webhook 使用 HMAC 验签。</small>
    </div>

    <div v-if="integrationsQuery.isError.value" class="panel-state panel-state--error">
      外部集成配置加载失败，请确认管理员权限。
    </div>
    <div v-else-if="integrationsQuery.isLoading.value" class="panel-state">正在加载集成 provider…</div>

    <section v-else class="provider-grid">
      <article v-for="integration in integrations" :key="integration.provider" class="provider-card">
        <header>
          <div>
            <strong>{{ providerLabel(integration.provider) }}</strong>
            <span :class="['status-pill', `status-pill--${integration.status}`]">
              {{ integrationStatusLabel(integration.status) }}
            </span>
          </div>
          <label class="provider-toggle">
            <input v-model="enabledDrafts[integration.provider]" type="checkbox" />
            <span>{{ enabledDrafts[integration.provider] ? "启用" : "停用" }}</span>
          </label>
        </header>

        <div class="config-grid">
          <label v-for="key in [...integration.required_config, ...optionalConfigKeys(integration.provider)]" :key="key">
            <span>{{ key }}</span>
            <input
              v-model="configDrafts[integration.provider][key]"
              :type="key.includes('secret') || key.includes('token') ? 'password' : 'text'"
              :placeholder="integration.required_config.includes(key) ? '必填' : '可选'"
            />
          </label>
        </div>

        <p v-if="integration.issues.length" class="issue-list">
          配置问题：{{ integration.issues.join("、") }}
        </p>
        <p v-else-if="integration.last_error" class="issue-list">最近错误：{{ integration.last_error }}</p>
        <p v-else class="provider-note">最近检查：{{ integration.last_checked_at ? relativeTime(integration.last_checked_at) : "未检查" }}</p>

        <UiButton tone="subtle" :disabled="updateIntegration.isPending.value" @click="saveProvider(integration.provider)">
          保存 {{ providerLabel(integration.provider) }}
        </UiButton>
      </article>
    </section>

    <section class="github-unfurl">
      <h3>GitHub Issue 展开</h3>
      <label>
        <span>Issue URL</span>
        <input v-model="issueUrl" placeholder="https://github.com/org/repo/issues/1" />
      </label>
      <article v-if="issuePreviewQuery.data.value" class="issue-preview">
        <strong>{{ issuePreviewQuery.data.value.title }}</strong>
        <span>
          {{ issuePreviewQuery.data.value.owner }}/{{ issuePreviewQuery.data.value.repo }}#{{ issuePreviewQuery.data.value.number }}
          · {{ issuePreviewQuery.data.value.source === "webhook_cache" ? "来自 webhook 缓存" : "URL 解析" }}
        </span>
      </article>
    </section>

    <section class="external-events">
      <h3>最近外部事件</h3>
      <div v-if="events.length" class="event-list">
        <article v-for="event in events" :key="event.id">
          <div>
            <strong>{{ providerLabel(event.provider) }} · {{ event.event_type }} · {{ event.status }}</strong>
            <span>{{ event.title ?? event.linked_resource_id ?? event.event_id }}</span>
            <small>{{ event.retry_count }}/{{ event.max_retries }} 重试 · {{ relativeTime(event.created_at) }}</small>
          </div>
          <UiButton
            tone="ghost"
            :disabled="retryEvent.isPending.value || event.retry_count >= event.max_retries"
            @click="retryEvent.mutate(event.id)"
          >
            重试
          </UiButton>
        </article>
      </div>
      <p v-else class="panel-state">暂无外部事件。</p>
    </section>
  </UiCard>
</template>

<style scoped lang="scss" src="./AdminExternalIntegrationsPanel.scss"></style>
