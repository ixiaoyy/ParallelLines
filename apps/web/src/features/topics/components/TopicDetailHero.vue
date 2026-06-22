<script setup lang="ts">
import type { TopicCardVM } from "@/entities/topic/model";
import { tagToneClass } from "@/shared/theme/boardPalette";
import UiBadge from "@/shared/ui/Badge.vue";

defineProps<{
  topic: TopicCardVM;
}>();
</script>

<template>
  <section class="topic-detail-hero" :style="{ '--topic-color': topic.boardColor }" aria-labelledby="topic-title">
    <nav class="topic-breadcrumb" aria-label="主题位置">
      <RouterLink :to="{ name: 'board-detail', params: { slug: topic.boardSlug } }">
        {{ topic.boardName }}
      </RouterLink>
    </nav>

    <h1 id="topic-title">{{ topic.title }}</h1>

    <div class="topic-taxonomy" aria-label="主题标签与状态">
      <UiBadge v-if="topic.pinned" tone="amber">置顶</UiBadge>
      <UiBadge v-if="topic.featured" tone="green">精华</UiBadge>
      <UiBadge v-if="topic.solved" tone="green">已解决</UiBadge>
      <UiBadge v-if="topic.status === 'closed'" tone="gray">已关闭</UiBadge>
      <RouterLink
        v-for="tag in topic.tags"
        :key="tag"
        class="tone-chip"
        :class="tagToneClass(tag)"
        :to="{ name: 'search', query: { q: tag, tag } }"
      >
        #{{ tag }}
      </RouterLink>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./TopicDetailHero.scss"></style>
