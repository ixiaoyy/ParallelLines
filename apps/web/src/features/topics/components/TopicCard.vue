<script setup lang="ts">
import { CheckCircleOutlined, DeleteOutlined, EllipsisOutlined, LockOutlined } from "@ant-design/icons-vue";
import { computed } from "vue";

import type { TopicCardVM } from "@/entities/topic/model";
import { resolveApiAssetUrl } from "@/shared/api/client";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import { boardToneClass, tagToneClass } from "@/shared/theme/boardPalette";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiBadge from "@/shared/ui/Badge.vue";

const props = withDefaults(
  defineProps<{
    topic: TopicCardVM;
    canDeleteTopic?: boolean;
    deletingTopic?: boolean;
    appearance?: "default" | "profile";
  }>(),
  {
    canDeleteTopic: false,
    deletingTopic: false,
    appearance: "default",
  },
);

const emit = defineEmits<{
  deleteTopic: [topic: TopicCardVM];
}>();

const topicRoute = computed(() => topicDetailRoute(props.topic));

const answerState = computed(() => {
  if (props.topic.status === "closed" || props.topic.status === "archived") {
    return { tone: "closed", label: "已关闭", helper: "暂停回复" };
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
    return { tone: "featured", label: "精华", helper: "推荐阅读" };
  }

  return { tone: "open", label: "讨论中", helper: "继续跟进" };
});

// Emits the selected topic to the parent-owned destructive delete flow.
// Key parameters: none. Return value: none; side effect is an event when the button is available.
function requestDeleteTopic() {
  if (!props.canDeleteTopic || props.deletingTopic) {
    return;
  }

  emit("deleteTopic", props.topic);
}
</script>

<template>
  <article
    class="topic-row"
    :class="[
      boardToneClass(topic.boardSlug),
      `topic-row--${appearance}`,
      { 'topic-row--pinned': topic.pinned, 'topic-row--with-admin-actions': canDeleteTopic },
    ]"
  >
    <RouterLink
      class="topic-row-hit"
      :to="topicRoute"
      :aria-label="`打开主题：${topic.title}`"
      tabindex="-1"
      aria-hidden="true"
    />
    <UiAvatar
      v-if="appearance === 'profile'"
      class="topic-profile-avatar"
      :src="resolveApiAssetUrl(topic.authorAvatarUrl)"
      :name="topic.authorName"
      :role="topic.authorRole"
      :level="topic.authorLevel"
      size="sm"
      :title="topic.authorName"
    />
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
        <RouterLink
          class="category-chip tone-chip"
          :class="boardToneClass(topic.boardSlug)"
          :to="{ name: 'board-detail', params: { slug: topic.boardSlug } }"
        >
          <span class="category-dot tone-mark-dot" aria-hidden="true"></span>
          {{ topic.boardName }}
        </RouterLink>

        <RouterLink
          v-for="tag in topic.tags"
          :key="tag"
          class="topic-tag tone-chip"
          :class="tagToneClass(tag)"
          :to="{ name: 'search', query: { q: tag, tag } }"
        >
          #{{ tag }}
        </RouterLink>
      </div>

      <div v-if="appearance !== 'profile'" class="participant-strip" aria-label="发起人">
        <UiAvatar
          :src="resolveApiAssetUrl(topic.authorAvatarUrl)"
          :name="topic.authorName"
          :role="topic.authorRole"
          :level="topic.authorLevel"
          size="sm"
          :title="topic.authorName"
        />
        <span>
          {{ topic.authorName }} 发起 · {{ relativeTime(topic.lastPostedAt) }}有新动静
        </span>
      </div>
    </div>

    <div class="answer-state" :class="`answer-state--${answerState.tone}`">
      <CheckCircleOutlined v-if="answerState.tone === 'solved'" />
      <LockOutlined v-else-if="answerState.tone === 'closed'" />
      <strong>{{ answerState.label }}</strong>
      <small>{{ answerState.helper }}</small>
    </div>

    <div class="topic-stat">
      <strong>{{ compactNumber(topic.replyCount) }}</strong>
      <span>回复</span>
    </div>

    <div class="topic-activity">
      <strong>{{ relativeTime(topic.lastPostedAt) }}</strong>
      <span>{{ topic.authorName }}</span>
    </div>

    <div v-if="canDeleteTopic" class="topic-admin-actions" @click.stop>
      <details v-if="appearance === 'profile'" class="topic-overflow-menu">
        <summary :aria-label="`主题操作：${topic.title}`" :title="`主题操作：${topic.title}`">
          <EllipsisOutlined aria-hidden="true" />
        </summary>
        <div>
          <button
            class="topic-delete-button"
            type="button"
            :disabled="deletingTopic"
            :aria-label="`删除主题：${topic.title}`"
            @click.stop.prevent="requestDeleteTopic"
          >
            <DeleteOutlined aria-hidden="true" />
            <span>{{ deletingTopic ? "删除中" : "删除主题" }}</span>
          </button>
        </div>
      </details>
      <button
        v-else
        class="topic-delete-button"
        type="button"
        :disabled="deletingTopic"
        :aria-label="`删除主题：${topic.title}`"
        :title="`删除主题：${topic.title}`"
        @click.stop.prevent="requestDeleteTopic"
      >
        <DeleteOutlined aria-hidden="true" />
        <span>{{ deletingTopic ? "删除中" : "删除" }}</span>
      </button>
    </div>
  </article>
</template>

<style scoped lang="scss" src="./TopicCard.scss"></style>
