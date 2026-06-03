<script setup lang="ts">
import { computed } from "vue";

import type { TopicCardVM } from "@/entities/topic/model";
import TopicCard from "@/features/topics/components/TopicCard.vue";

const props = withDefaults(
  defineProps<{
    topics: TopicCardVM[];
    emptyTitle?: string;
    emptyDescription?: string;
  }>(),
  {
    emptyTitle: "还没有帖子",
    emptyDescription: "可以稍后再来看看。",
  },
);

// orderedTopics 用途：在最终渲染层确保置顶帖优先展示，同时保持同组内原有顺序；无参数，返回排序后的展示列表且不修改源数组。
const orderedTopics = computed(() =>
  props.topics
    .map((topic, index) => ({ topic, index }))
    .sort((left, right) => Number(right.topic.pinned) - Number(left.topic.pinned) || left.index - right.index)
    .map(({ topic }) => topic),
);
</script>

<template>
  <section class="topic-list-shell" aria-labelledby="topic-list-heading">
    <header class="topic-list-header">
      <h2 id="topic-list-heading">主题</h2>
      <span>状态</span>
      <span>回复</span>
      <span>互动</span>
      <span>活动</span>
    </header>

    <div v-if="orderedTopics.length" class="topic-list">
      <TopicCard v-for="topic in orderedTopics" :key="topic.id" :topic="topic" />
    </div>

    <div v-else class="topic-list-empty">
      <strong>{{ emptyTitle }}</strong>
      <span>{{ emptyDescription }}</span>
    </div>

    <footer v-if="orderedTopics.length" class="topic-list-footer">
      <span>已经到底啦 🎉</span>
    </footer>
  </section>
</template>

<style scoped lang="scss" src="./TopicList.scss"></style>
