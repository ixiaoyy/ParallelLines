<script setup lang="ts">
import { uiText } from "@/shared/i18n/locale";
import { ref } from "vue";

import { useSimilarTopics } from "@/features/ai/queries";
import UiButton from "@/shared/ui/Button.vue";

const props = defineProps<{
  title: string;
  body: string;
  tags: string[];
}>();

const similarMutation = useSimilarTopics();
const status = ref("");

function findSimilar() {
  if (props.title.trim().length < 2) {
    status.value = "先写一个更明确的标题，再查找相似主题。";
    return;
  }
  status.value = "";
  similarMutation.mutate({
    title: props.title,
    raw_md: props.body,
    tags: props.tags,
    limit: 5,
  });
}
</script>

<template>
  <section class="similar-topic-hints" :aria-label="uiText('AI 相似主题推荐')">
    <div>
      <strong>{{ uiText("相似主题推荐") }}</strong>
      <span>{{ uiText("发布前先查重，减少重复讨论；AI 建议不会自动修改你的内容。") }}</span>
    </div>
    <UiButton type="button" tone="ghost" :disabled="similarMutation.isPending.value" @click="findSimilar">
      {{ similarMutation.isPending.value ? uiText("查找中…") : uiText("查找相似主题") }}
    </UiButton>
    <p v-if="status" class="hint-status">{{ uiText(status) }}</p>
    <ol v-if="similarMutation.data.value?.length" class="similar-list">
      <li v-for="topic in similarMutation.data.value" :key="topic.id">
        <RouterLink :to="{ name: 'topic-detail', params: { id: topic.id, slug: topic.slug } }">
          {{ topic.title }}
        </RouterLink>
        <small>{{ topic.board_name }} · {{ uiText("匹配词：{terms}", { terms: topic.matched_terms.join(" / ") }) }}</small>
      </li>
    </ol>
    <p v-else-if="similarMutation.isSuccess.value" class="hint-status">{{ uiText("未发现明显重复主题。") }}</p>
  </section>
</template>

<style scoped lang="scss" src="./SimilarTopicHints.scss"></style>
