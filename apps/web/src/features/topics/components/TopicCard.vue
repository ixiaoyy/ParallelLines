<script setup lang="ts">
import { CheckCircleOutlined, LockOutlined } from "@ant-design/icons-vue";
import { computed } from "vue";

import type { TopicCardVM } from "@/entities/topic/model";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiBadge from "@/shared/ui/Badge.vue";

const props = defineProps<{ topic: TopicCardVM }>();

const visiblePosters = computed(() => props.topic.posterNames.slice(0, 4));
const hiddenPosterCount = computed(() =>
  Math.max(props.topic.posterNames.length - visiblePosters.value.length, 0),
);

const topicUrl = computed(() => `/t/${props.topic.slug}/${props.topic.id}`);
</script>

<template>
  <article class="topic-row" :class="{ 'topic-row--pinned': topic.pinned }">
    <div class="topic-main">
      <div class="topic-title-line">
        <UiBadge v-if="topic.pinned" tone="amber">置顶</UiBadge>
        <UiBadge v-if="topic.featured" tone="green">精华</UiBadge>
        <UiBadge v-if="topic.unreadCount" tone="blue">{{ topic.unreadCount }} 新</UiBadge>
        <LockOutlined v-if="topic.status === 'closed'" class="topic-status-icon" aria-label="已关闭" />
        <RouterLink class="topic-title" :to="topicUrl">{{ topic.title }}</RouterLink>
      </div>

      <p class="topic-excerpt">{{ topic.excerpt }}</p>

      <div class="topic-meta-line">
        <span class="category-chip" :style="{ '--category-color': topic.boardColor }">
          <span class="category-dot" aria-hidden="true"></span>
          {{ topic.boardName }}
        </span>

        <span v-for="tag in topic.tags" :key="tag" class="topic-tag">#{{ tag }}</span>

        <span v-if="topic.solved" class="solved-chip">
          <CheckCircleOutlined />
          已解决
        </span>
      </div>
    </div>

    <div class="posters" aria-label="参与者">
      <UiAvatar
        v-for="poster in visiblePosters"
        :key="poster"
        :name="poster"
        size="sm"
        :title="poster"
      />
      <span v-if="hiddenPosterCount" class="posters-more">+{{ hiddenPosterCount }}</span>
    </div>

    <div class="topic-stat">
      <strong>{{ compactNumber(topic.replyCount) }}</strong>
      <span>回复</span>
    </div>

    <div class="topic-stat topic-stat--views">
      <strong>{{ compactNumber(topic.viewCount) }}</strong>
      <span>浏览</span>
    </div>

    <div class="topic-activity">
      <strong>{{ relativeTime(topic.lastPostedAt) }}</strong>
      <span>{{ topic.authorName }}</span>
    </div>
  </article>
</template>

<style scoped lang="scss" src="./TopicCard.scss"></style>
