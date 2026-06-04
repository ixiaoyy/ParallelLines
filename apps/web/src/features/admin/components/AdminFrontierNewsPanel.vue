<script setup lang="ts">
import { computed, ref } from "vue";

import {
  frontierNewsStatusLabel,
  type FrontierNewsItemResponse,
  type FrontierNewsSourceResponse,
} from "@/features/admin/model";
import {
  useCollectFrontierNews,
  useCollectFrontierNewsSource,
  useEnrichFrontierNewsItem,
  useFrontierNewsItems,
  useFrontierNewsSources,
  useQueueFrontierNewsItem,
  useUpdateFrontierNewsSource,
} from "@/features/admin/queries";
import { relativeTime } from "@/shared/lib/format";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const itemStatus = ref("review_pending");
const actionNotice = ref("");

const sourcesQuery = useFrontierNewsSources();
const itemsQuery = useFrontierNewsItems(() => ({ status: itemStatus.value, limit: 20 }));
const updateSourceMutation = useUpdateFrontierNewsSource();
const collectAllMutation = useCollectFrontierNews();
const collectSourceMutation = useCollectFrontierNewsSource();
const enrichMutation = useEnrichFrontierNewsItem();
const queueMutation = useQueueFrontierNewsItem();

const sources = computed(() => sourcesQuery.data.value ?? []);
const items = computed(() => itemsQuery.data.value ?? []);
const pending = computed(
  () =>
    collectAllMutation.isPending.value ||
    collectSourceMutation.isPending.value ||
    updateSourceMutation.isPending.value ||
    enrichMutation.isPending.value ||
    queueMutation.isPending.value,
);

/**
 * Maps backend source kinds to short labels for source cards.
 *
 * @param kind - Raw source kind returned by the admin API.
 * @returns Human-readable source type label.
 */
function sourceKindLabel(kind: string): string {
  const labels: Record<string, string> = {
    rss: "RSS/Atom",
    arxiv: "arXiv",
    hacker_news: "Hacker News",
    github_search: "GitHub Search",
  };
  return labels[kind] ?? kind;
}

/**
 * Chooses a badge tone that reflects material processing state.
 *
 * @param status - Raw frontier material status.
 * @returns UiBadge tone name used by the card header.
 */
function itemTone(status: string): "green" | "amber" | "blue" | "gray" | "coral" {
  if (status === "published") return "green";
  if (status === "review_pending") return "blue";
  if (status === "failed" || status === "rejected") return "coral";
  if (status === "ai_pending" || status === "collected") return "amber";
  return "gray";
}

/**
 * Checks whether a material can still be sent to moderation manually.
 *
 * @param item - Frontier material row rendered in the list.
 * @returns True when no reviewable exists and the item is not terminal.
 */
function canQueue(item: FrontierNewsItemResponse): boolean {
  return !item.reviewable_id && !["published", "rejected", "duplicate"].includes(item.status);
}

/**
 * Formats collection counters into one compact operation notice.
 *
 * @param created - Number of newly persisted materials.
 * @param queued - Number of materials sent to moderation.
 * @param errors - Number of source/item errors.
 * @returns Localized summary text for the notice bar.
 */
function collectSummaryText(created: number, queued: number, errors: number): string {
  return `采集完成：新增 ${created} 条，送审 ${queued} 条，错误 ${errors} 个。`;
}

/**
 * Starts all-source manual collection and updates the operation notice.
 *
 * Side effect: triggers a Vue Query mutation that refreshes frontier/moderation caches.
 */
function runCollectAll() {
  actionNotice.value = "正在采集全部启用来源…";
  collectAllMutation.mutate(undefined, {
    onSuccess: (result) => {
      actionNotice.value = collectSummaryText(result.created_count, result.queued_count, result.error_count);
    },
    onError: (error) => {
      actionNotice.value = `采集失败：${error.message}`;
    },
  });
}

/**
 * Starts manual collection for one source card.
 *
 * @param source - Source row whose API ID is passed to the mutation.
 * Side effect: updates the operation notice and refreshes frontier/moderation caches.
 */
function collectSource(source: FrontierNewsSourceResponse) {
  actionNotice.value = `正在采集 ${source.name}…`;
  collectSourceMutation.mutate(source.id, {
    onSuccess: (result) => {
      actionNotice.value = `${source.name}：${collectSummaryText(
        result.created_count,
        result.queued_count,
        result.error_count,
      )}`;
    },
    onError: (error) => {
      actionNotice.value = `${source.name} 采集失败：${error.message}`;
    },
  });
}

/**
 * Enables or disables a source without changing the rest of its config.
 *
 * @param source - Source row to toggle.
 * Side effect: persists enabled state through the admin API.
 */
function toggleSource(source: FrontierNewsSourceResponse) {
  updateSourceMutation.mutate({
    sourceId: source.id,
    payload: { enabled: !source.enabled },
  });
}

/**
 * Re-runs deterministic AI整理 for one material.
 *
 * @param item - Material row whose ID is sent to the enrichment endpoint.
 * Side effect: may create or update the linked moderation reviewable.
 */
function rerunAi(item: FrontierNewsItemResponse) {
  actionNotice.value = `正在重新整理：${item.title}`;
  enrichMutation.mutate(item.id, {
    onSuccess: () => {
      actionNotice.value = "AI 整理完成，符合条件的素材已进入统一审核队列。";
    },
  });
}

/**
 * Manually sends a prepared material into the existing moderation queue.
 *
 * @param item - Material row to queue for moderator approval.
 * Side effect: creates a queued_topic reviewable that auto-publishes on approval.
 */
function queueItem(item: FrontierNewsItemResponse) {
  queueMutation.mutate(
    { itemId: item.id, note: "管理员手动送审前沿资讯素材。" },
    {
      onSuccess: () => {
        actionNotice.value = "已送入统一审核队列，审核通过后将自动发布。";
      },
    },
  );
}
</script>

<template>
  <UiCard class="frontier-news-panel">
    <div class="section-head frontier-news-panel__head">
      <div class="title-area">
        <span class="panel-kicker">Frontier</span>
        <h2>前沿资讯素材池</h2>
        <p>定时任务采集白名单来源，AI 先整理成中文，再进入现有审核台；通过后自动由「资讯机器人」发布。</p>
      </div>
      <div class="frontier-news-panel__actions">
        <RouterLink class="review-link" :to="{ name: 'admin-moderation' }">去审核台</RouterLink>
        <UiButton tone="primary" :disabled="pending" @click="runCollectAll">
          {{ collectAllMutation.isPending.value ? "采集中…" : "立即采集" }}
        </UiButton>
      </div>
    </div>

    <p v-if="actionNotice" class="frontier-news-panel__notice">{{ actionNotice }}</p>

    <section class="frontier-news-panel__sources" aria-labelledby="frontier-sources-title">
      <h3 id="frontier-sources-title">信息源</h3>
      <p v-if="sourcesQuery.isPending.value" class="panel-state">正在读取默认来源…</p>
      <p v-else-if="sourcesQuery.isError.value" class="panel-state panel-state--error">信息源暂不可用。</p>
      <div v-else class="source-grid">
        <article v-for="source in sources" :key="source.id" class="source-card">
          <div>
            <strong>{{ source.name }}</strong>
            <span>{{ sourceKindLabel(source.kind) }} · 每 {{ source.fetch_interval_minutes }} 分钟</span>
          </div>
          <UiBadge :tone="source.enabled ? 'green' : 'gray'">{{ source.enabled ? "启用" : "停用" }}</UiBadge>
          <p class="source-url">{{ source.url }}</p>
          <p v-if="source.last_error" class="source-error">{{ source.last_error }}</p>
          <div class="source-card__actions">
            <UiButton tone="subtle" :disabled="pending" @click="collectSource(source)">采集此源</UiButton>
            <UiButton tone="ghost" :disabled="pending" @click="toggleSource(source)">
              {{ source.enabled ? "停用" : "启用" }}
            </UiButton>
          </div>
        </article>
      </div>
    </section>

    <section class="frontier-news-panel__items" aria-labelledby="frontier-items-title">
      <div class="items-head">
        <h3 id="frontier-items-title">最近素材</h3>
        <select v-model="itemStatus" aria-label="素材状态筛选">
          <option value="review_pending">审核中</option>
          <option value="collected">已采集</option>
          <option value="failed">失败</option>
          <option value="published">已发布</option>
          <option value="rejected">已拒绝</option>
          <option value="all">全部</option>
        </select>
      </div>
      <p v-if="itemsQuery.isPending.value" class="panel-state">正在加载素材…</p>
      <p v-else-if="itemsQuery.isError.value" class="panel-state panel-state--error">素材池暂不可用。</p>
      <div v-else-if="items.length" class="item-list">
        <article v-for="item in items" :key="item.id" class="item-card">
          <div class="item-card__meta">
            <UiBadge :tone="itemTone(item.status)">{{ frontierNewsStatusLabel(item.status) }}</UiBadge>
            <span>{{ item.source_name || "未知来源" }} · {{ relativeTime(item.created_at) }}</span>
            <span>评分 {{ item.score }}</span>
          </div>
          <h4>{{ item.ai_title_zh || item.title }}</h4>
          <p>{{ item.ai_summary_zh || item.summary || "暂无摘要" }}</p>
          <div v-if="item.suggested_tags.length" class="tag-row">
            <span v-for="tag in item.suggested_tags" :key="tag">{{ tag }}</span>
          </div>
          <div class="item-card__actions">
            <a :href="item.canonical_url" target="_blank" rel="noreferrer">查看原文</a>
            <RouterLink v-if="item.reviewable_id" :to="{ name: 'admin-moderation' }">审核</RouterLink>
            <RouterLink v-if="item.topic_id" :to="{ name: 'topic-detail', params: { id: item.topic_id } }">已发布主题</RouterLink>
            <UiButton tone="subtle" :disabled="pending" @click="rerunAi(item)">重新整理</UiButton>
            <UiButton v-if="canQueue(item)" tone="primary" :disabled="pending" @click="queueItem(item)">送审</UiButton>
          </div>
        </article>
      </div>
      <p v-else class="panel-state">当前筛选下暂无素材。</p>
    </section>
  </UiCard>
</template>

<style scoped lang="scss" src="./AdminFrontierNewsPanel.scss"></style>
