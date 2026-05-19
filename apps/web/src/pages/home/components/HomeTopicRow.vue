<script setup lang="ts">
import type { TopicCardVM } from "@/entities/topic/model";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import { topicDetailRoute } from "@/shared/router/topicRoutes";

defineProps<{ topic: TopicCardVM }>();
</script>

<template>
  <article class="home-topic-row">
    <div class="topic-main">
      <div class="author-avatar-wrapper" aria-hidden="true">
        <div class="author-avatar">{{ topic.authorName.slice(0, 1).toUpperCase() }}</div>
        <span class="board-badge-dot" :style="{ '--board-color': topic.boardColor }" :title="topic.boardName"></span>
      </div>
      <div class="topic-copy">
        <div class="topic-title-line">
          <RouterLink class="topic-title" :to="topicDetailRoute(topic)">{{ topic.title }}</RouterLink>
          <span v-if="topic.pinned" class="topic-status">置顶</span>
          <span v-if="topic.featured" class="topic-status topic-status--signal">精选</span>
          <span v-if="topic.solved" class="topic-status topic-status--solved">已解决</span>
        </div>
        <p>{{ topic.excerpt }}</p>
        <div class="topic-tags">
          <RouterLink
            class="board-chip"
            :to="{ name: 'board-detail', params: { slug: topic.boardSlug } }"
            :style="{ '--board-color': topic.boardColor }"
          >
            {{ topic.boardName }}
          </RouterLink>
          <RouterLink
            v-for="tag in topic.tags.slice(0, 3)"
            :key="tag"
            :to="{ name: 'search', query: { q: tag, tag } }"
          >
            #{{ tag }}
          </RouterLink>
        </div>
      </div>
    </div>
    <div class="metric">{{ compactNumber(topic.replyCount) }}</div>
    <div class="metric">{{ compactNumber(topic.viewCount) }}</div>
    <div class="activity">{{ relativeTime(topic.lastPostedAt) }}</div>
  </article>
</template>

<style scoped lang="scss" src="./HomeTopicRow.scss"></style>
