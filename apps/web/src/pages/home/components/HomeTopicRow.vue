<script setup lang="ts">
import type { TopicCardVM } from "@/entities/topic/model";
import { resolveApiAssetUrl } from "@/shared/api/client";
import { boardToneClass, tagToneClass } from "@/shared/theme/boardPalette";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import UiAvatar from "@/shared/ui/Avatar.vue";

defineProps<{ topic: TopicCardVM }>();
</script>

<template>
  <article class="home-topic-row" :class="boardToneClass(topic.boardSlug)">
    <RouterLink
      class="home-topic-hit"
      :to="topicDetailRoute(topic)"
      :aria-label="`打开主题：${topic.title}`"
      tabindex="-1"
      aria-hidden="true"
    />
    <div class="topic-main">
      <div class="author-avatar-wrapper" aria-hidden="true">
        <UiAvatar
          :src="resolveApiAssetUrl(topic.authorAvatarUrl)"
          :name="topic.authorName"
          :role="topic.authorRole"
          :level="topic.authorLevel"
          size="sm"
        />
      </div>
      <div class="topic-copy">
        <div class="topic-title-line">
          <RouterLink class="topic-title" :to="topicDetailRoute(topic)">{{ topic.title }}</RouterLink>
          <span v-if="topic.pinned" class="topic-status">置顶</span>
          <span v-if="topic.tags.includes('今日节目')" class="topic-status topic-status--program">今日节目</span>
          <span v-if="topic.featured" class="topic-status topic-status--signal">精选</span>
          <span v-if="topic.solved" class="topic-status topic-status--solved">已解决</span>
        </div>
        <p>{{ topic.excerpt }}</p>
        <div class="topic-tags">
          <RouterLink
            class="board-chip tone-chip"
            :class="boardToneClass(topic.boardSlug)"
            :to="{ name: 'board-detail', params: { slug: topic.boardSlug } }"
          >
            {{ topic.boardName }}
          </RouterLink>
          <RouterLink
            v-for="tag in topic.tags.slice(0, 3)"
            :key="tag"
            class="tone-chip"
            :class="tagToneClass(tag)"
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
