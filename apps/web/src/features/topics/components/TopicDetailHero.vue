<script setup lang="ts">
import type { TopicCardVM } from "@/entities/topic/model";
import { relativeTime } from "@/shared/lib/format";
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
    <div class="topic-detail-hero__main">
      <nav class="topic-breadcrumb" aria-label="主题位置">
        <RouterLink to="/boards">版块</RouterLink>
        <span aria-hidden="true">/</span>
        <RouterLink :to="{ name: 'board-detail', params: { slug: topic.boardSlug } }">
          {{ topic.boardName }}
        </RouterLink>
      </nav>

      <div class="topic-title-block">
        <div class="topic-badges" aria-label="主题状态">
          <UiBadge v-if="topic.pinned" tone="amber">置顶</UiBadge>
          <UiBadge v-if="topic.featured" tone="green">精华</UiBadge>
          <UiBadge v-if="topic.solved" tone="green">已解决</UiBadge>
          <UiBadge v-if="topic.status === 'closed'" tone="gray">已关闭</UiBadge>
        </div>
        <h1 id="topic-title">{{ topic.title }}</h1>
        <p>{{ topic.excerpt }}</p>
      </div>

      <div class="topic-author-strip">
        <UiAvatar :name="topic.authorName" size="lg" />
        <div>
          <span>发起人</span>
          <strong>{{ topic.authorName }}</strong>
        </div>
        <time>{{ relativeTime(topic.lastPostedAt) }}有新回复</time>
      </div>
    </div>

    <dl class="topic-stat-grid" aria-label="主题统计">
      <div v-for="item in stats" :key="item.label">
        <dt>{{ item.label }}</dt>
        <dd>{{ item.value }}</dd>
      </div>
    </dl>
  </section>
</template>

<style scoped lang="scss" src="./TopicDetailHero.scss"></style>
