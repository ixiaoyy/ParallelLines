<script setup lang="ts">
import { currentLocale, uiText } from "@/shared/i18n/locale";
import { computed } from "vue";

import type { TopicCardVM } from "@/entities/topic/model";
import TopicCard from "@/features/topics/components/TopicCard.vue";

const props = withDefaults(
  defineProps<{
    topics: TopicCardVM[];
    emptyTitle?: string;
    emptyDescription?: string;
    canDeleteTopics?: boolean;
    deletingTopicId?: string | null;
    appearance?: "default" | "profile";
  }>(),
  {
    emptyTitle: "还没有主题",
    emptyDescription: "可以稍后再来看看。",
    canDeleteTopics: false,
    deletingTopicId: null,
    appearance: "default",
  },
);

const emit = defineEmits<{
  deleteTopic: [topic: TopicCardVM];
}>();

// orderedTopics 用途：在最终渲染层确保置顶帖优先展示，同时保持同组内原有顺序；无参数，返回排序后的展示列表且不修改源数组。
const orderedTopics = computed(() =>
  props.topics
    .map((topic, index) => ({ topic, index }))
    .sort((left, right) => Number(right.topic.pinned) - Number(left.topic.pinned) || left.index - right.index)
    .map(({ topic }) => topic),
);
</script>

<template>
  <section
    class="topic-list-shell"
    :class="`topic-list-shell--${appearance}`"
    aria-labelledby="topic-list-heading"
  >
    <header class="topic-list-header">
      <h2 id="topic-list-heading">{{ uiText("主题") }}</h2>
      <span>{{ uiText("状态") }}</span>
      <span>{{ uiText("回复") }}</span>
      <span>{{ uiText("互动") }}</span>
      <span>{{ currentLocale === "en-US" ? uiText("主题活动") : uiText("活动") }}</span>
    </header>

    <div v-if="orderedTopics.length" class="topic-list">
      <TopicCard
        v-for="topic in orderedTopics"
        :key="topic.id"
        :topic="topic"
        :can-delete-topic="canDeleteTopics"
        :deleting-topic="deletingTopicId === topic.id"
        :appearance="appearance"
        @delete-topic="emit('deleteTopic', $event)"
      />
    </div>

    <div v-else class="topic-list-empty">
      <strong>{{ uiText(emptyTitle) }}</strong>
      <span>{{ uiText(emptyDescription) }}</span>
    </div>

    <footer v-if="orderedTopics.length" class="topic-list-footer">
      <span>{{ uiText("已经到底啦 🎉") }}</span>
    </footer>
  </section>
</template>

<style scoped lang="scss" src="./TopicList.scss"></style>
