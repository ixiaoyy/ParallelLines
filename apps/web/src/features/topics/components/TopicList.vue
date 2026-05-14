<script setup lang="ts">
import type { TopicCardVM } from "@/entities/topic/model";
import TopicCard from "@/features/topics/components/TopicCard.vue";

defineProps<{ topics: TopicCardVM[] }>();
</script>

<template>
  <section class="topic-list-shell" aria-labelledby="topic-list-heading">
    <header class="topic-list-header">
      <h2 id="topic-list-heading">主题</h2>
      <span>参与者</span>
      <span>回复</span>
      <span class="views-heading">浏览</span>
      <span>活动</span>
    </header>

    <div class="topic-list">
      <TopicCard v-for="topic in topics" :key="topic.id" :topic="topic" />
    </div>

    <footer class="topic-list-footer">
      <button type="button">加载更多主题</button>
    </footer>
  </section>
</template>

<style scoped lang="scss" src="./TopicList.scss"></style>
