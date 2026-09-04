<script setup lang="ts">
import { DeleteOutlined } from "@ant-design/icons-vue";

import type { TopicCardVM } from "@/entities/topic/model";
import OperatorIdentityBadge from "@/features/users/components/OperatorIdentityBadge.vue";
import { boardToneClass, tagToneClass } from "@/shared/theme/boardPalette";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import UiAvatar from "@/shared/ui/Avatar.vue";

const props = withDefaults(
  defineProps<{
    topic: TopicCardVM;
    canDeleteTopic?: boolean;
    deletingTopic?: boolean;
  }>(),
  {
    canDeleteTopic: false,
    deletingTopic: false,
  },
);

const emit = defineEmits<{
  deleteTopic: [topic: TopicCardVM];
}>();

// Emits the row topic to the parent-owned administrator delete flow.
// Key parameters: none. Return value: none; side effect is a deleteTopic event when available.
function requestDeleteTopic() {
  if (!props.canDeleteTopic || props.deletingTopic) {
    return;
  }

  emit("deleteTopic", props.topic);
}
</script>

<template>
  <article
    class="home-topic-row"
    :class="[boardToneClass(topic.boardSlug), { 'home-topic-row--with-admin-actions': canDeleteTopic }]"
  >
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
          :src="topic.authorAvatarUrl"
          :name="topic.authorName"
          :role="topic.authorRole"
          :level="topic.authorLevel"
          size="sm"
          thumbnail
          loading="lazy"
          decoding="async"
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
        <div class="topic-author" aria-label="发起人">
          <span>{{ topic.authorName }}</span>
          <OperatorIdentityBadge :is-persona="topic.authorIsPersona" :kind="topic.authorPersonaKind" />
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
    <div v-if="canDeleteTopic" class="admin-topic-actions">
      <button
        class="admin-topic-delete"
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

<style scoped lang="scss" src="./HomeTopicRow.scss"></style>
