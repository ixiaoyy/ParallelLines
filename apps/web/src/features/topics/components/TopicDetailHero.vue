<script setup lang="ts">
import type { TopicCardVM } from "@/entities/topic/model";
import { relativeTime } from "@/shared/lib/format";
import { tagToneClass } from "@/shared/theme/boardPalette";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiBadge from "@/shared/ui/Badge.vue";

export interface TopicHeroStat {
  label: string;
  value: string;
}

defineProps<{
  topic: TopicCardVM;
  stats: TopicHeroStat[];
}>();
</script>

<template>
  <section class="topic-detail-hero" :style="{ '--topic-color': topic.boardColor }" aria-labelledby="topic-title">
    <nav class="topic-breadcrumb" aria-label="主题位置">
      <RouterLink to="/boards">版块</RouterLink>
      <span aria-hidden="true">/</span>
      <RouterLink :to="{ name: 'board-detail', params: { slug: topic.boardSlug } }">
        {{ topic.boardName }}
      </RouterLink>
    </nav>

    <h1 id="topic-title">{{ topic.title }}</h1>

    <div class="topic-meta-row">
      <UiAvatar
        :src="topic.authorAvatarUrl"
        :name="topic.authorName"
        :role="topic.authorRole"
        :level="topic.authorLevel"
        size="sm"
      />
      <strong>{{ topic.authorName }}</strong>
      <time>{{ relativeTime(topic.lastPostedAt) }}有新动静</time>
    </div>

    <div class="topic-taxonomy" aria-label="主题分类与标签">
      <RouterLink class="board-chip" :to="{ name: 'board-detail', params: { slug: topic.boardSlug } }">
        {{ topic.boardName }}
      </RouterLink>
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

    <dl class="topic-stat-line" aria-label="主题统计">
      <div v-for="item in stats" :key="item.label">
        <dt>{{ item.label }}</dt>
        <dd>{{ item.value }}</dd>
      </div>
    </dl>
  </section>
</template>

<style scoped lang="scss" src="./TopicDetailHero.scss"></style>
