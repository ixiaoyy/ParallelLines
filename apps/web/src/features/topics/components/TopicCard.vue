<script setup lang="ts">
import { CheckCircleOutlined, LockOutlined, MessageOutlined } from "@ant-design/icons-vue";
import { computed } from "vue";

import type { TopicCardVM } from "@/entities/topic/model";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiBadge from "@/shared/ui/Badge.vue";

const props = defineProps<{ topic: TopicCardVM }>();

const topicRoute = computed(() => topicDetailRoute(props.topic));
const visiblePosterNames = computed(() => props.topic.posterNames.slice(0, 3));
const extraPosterCount = computed(() => Math.max(props.topic.posterNames.length - visiblePosterNames.value.length, 0));

const answerState = computed(() => {
  if (props.topic.status === "closed") {
    return { tone: "closed", label: "已关闭", helper: "只读归档" };
  }

  if (props.topic.solved) {
    return { tone: "solved", label: "已解决", helper: "优先参考" };
  }

  if (props.topic.officialReply) {
    return { tone: "official", label: "官方回复", helper: "团队已介入" };
  }

  if (props.topic.replyCount === 0) {
    return { tone: "unanswered", label: "未回复", helper: "等待首答" };
  }

  if (props.topic.featured) {
    return { tone: "featured", label: "精华", helper: "高信号" };
  }

  return { tone: "open", label: "讨论中", helper: "继续跟进" };
});

</script>

<template>
  <article class="topic-row" :class="{ 'topic-row--pinned': topic.pinned }">
    <div class="topic-main">
      <div class="topic-title-line">
        <UiBadge v-if="topic.pinned" tone="amber">置顶</UiBadge>
        <UiBadge v-if="topic.featured && !topic.solved" tone="green">精华</UiBadge>
        <UiBadge v-if="topic.unreadCount" tone="blue">{{ topic.unreadCount }} 新</UiBadge>
        <LockOutlined v-if="topic.status === 'closed'" class="topic-status-icon" aria-label="已关闭" />
        <RouterLink class="topic-title" :to="topicRoute">{{ topic.title }}</RouterLink>
      </div>

      <p class="topic-excerpt">{{ topic.excerpt }}</p>

      <div class="topic-meta-line">
        <span class="category-chip" :style="{ '--category-color': topic.boardColor }">
          <span class="category-dot" aria-hidden="true"></span>
          {{ topic.boardName }}
        </span>

        <span v-for="tag in topic.tags" :key="tag" class="topic-tag">#{{ tag }}</span>
      </div>

      <div class="participant-strip" aria-label="参与者">
        <div class="participant-avatars">
          <UiAvatar
            v-for="poster in visiblePosterNames"
            :key="poster"
            :name="poster"
            size="sm"
            :title="poster"
          />
          <span v-if="extraPosterCount" class="posters-more">+{{ extraPosterCount }}</span>
        </div>
        <span>{{ topic.authorName }} 发起 · {{ relativeTime(topic.lastPostedAt) }}有新动静</span>
      </div>
    </div>

    <div class="answer-state" :class="`answer-state--${answerState.tone}`">
      <CheckCircleOutlined v-if="answerState.tone === 'solved'" />
      <LockOutlined v-else-if="answerState.tone === 'closed'" />
      <strong>{{ answerState.label }}</strong>
      <small>{{ answerState.helper }}</small>
    </div>

    <div class="topic-stat">
      <div class="topic-stat__bubble">
        <MessageOutlined class="stat-icon" />
        <strong>{{ compactNumber(topic.replyCount) }}</strong>
      </div>
      <span>回复</span>
    </div>

    <div class="topic-activity">
      <strong>{{ relativeTime(topic.lastPostedAt) }}</strong>
      <span>{{ topic.authorName }}</span>
    </div>
  </article>
</template>

<style scoped lang="scss" src="./TopicCard.scss"></style>
