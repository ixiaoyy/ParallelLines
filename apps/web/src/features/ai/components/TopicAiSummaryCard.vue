<script setup lang="ts">
import { uiText } from "@/shared/i18n/locale";
import { computed } from "vue";

import { useRefreshTopicAiSummary, useTopicAiSummary } from "@/features/ai/queries";
import { hasAccessToken } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const props = defineProps<{ topicId: string }>();
const summaryQuery = useTopicAiSummary(computed(() => props.topicId));
const refreshSummary = useRefreshTopicAiSummary(computed(() => props.topicId));
const summary = computed(() => summaryQuery.data.value);

function refresh() {
  if (!hasAccessToken()) {
    return;
  }
  refreshSummary.mutate();
}
</script>

<template>
  <UiCard class="topic-ai-summary-card">
    <div class="ai-card-head">
      <div>
        <span>AI Assistant</span>
        <h2>{{ uiText("主题摘要") }}</h2>
      </div>
      <UiButton tone="subtle" :disabled="refreshSummary.isPending.value || !hasAccessToken()" @click="refresh">
        {{ refreshSummary.isPending.value ? uiText("生成中…") : summary ? uiText("刷新摘要") : uiText("生成摘要") }}
      </UiButton>
    </div>

    <p v-if="summaryQuery.isError.value && !summary" class="ai-muted">
      {{ uiText("暂无摘要。登录后可生成本地确定性摘要，输出仅作人工确认参考。") }}
    </p>
    <div v-else-if="summary" class="summary-body">
      <p>{{ summary.summary }}</p>
      <ul>
        <li v-for="point in summary.key_points" :key="point">{{ point }}</li>
      </ul>
      <small>
        {{ summary.model_name }} · {{ uiText("成本：{cost}", { cost: summary.cost_units }) }} · {{ relativeTime(summary.generated_at) }}
      </small>
    </div>
    <p v-else class="ai-muted">{{ uiText("点击生成摘要，快速定位长主题关键回复。") }}</p>
  </UiCard>
</template>

<style scoped lang="scss" src="./TopicAiSummaryCard.scss"></style>
