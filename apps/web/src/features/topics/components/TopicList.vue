<script setup lang="ts">
import type { TopicCardVM } from "@/entities/topic/model";
import TopicCard from "@/features/topics/components/TopicCard.vue";

defineProps<{ topics: TopicCardVM[] }>();
</script>

<template>
  <section class="topic-list-shell" aria-labelledby="topic-list-heading">
    <header class="topic-list-header">
      <h2 id="topic-list-heading">主题</h2>
      <span>状态</span>
      <span>回复</span>
      <span>活动</span>
    </header>

    <div v-if="topics.length" class="topic-list">
      <TopicCard v-for="topic in topics" :key="topic.id" :topic="topic" />
    </div>

    <div v-else class="topic-list-empty">
      <strong>没有符合条件的主题</strong>
      <span>清除筛选或换一个错误码、API 名称再试。</span>
    </div>

    <footer v-if="topics.length" class="topic-list-footer">
      <button type="button">加载更多主题</button>
    </footer>
  </section>
</template>

<style scoped lang="scss" src="./TopicList.scss"></style>
