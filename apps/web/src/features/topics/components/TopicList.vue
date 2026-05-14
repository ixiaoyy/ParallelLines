<script setup lang="ts">
import type { TopicCardVM } from "@/entities/topic/model";
import TopicCard from "@/features/topics/components/TopicCard.vue";

defineProps<{ topics: TopicCardVM[] }>();
</script>

<template>
  <div class="topic-list">
    <TopicCard v-for="topic in topics" :key="topic.id" :topic="topic" />
  </div>
</template>

<style scoped>
.topic-list {
  display: grid;
  gap: 0.9rem;
}
</style>
