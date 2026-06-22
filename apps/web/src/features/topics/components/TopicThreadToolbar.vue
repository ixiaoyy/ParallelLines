<script setup lang="ts">
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  EllipsisOutlined,
  FlagOutlined,
  FolderOpenOutlined,
  HeartFilled,
  HeartOutlined,
  LinkOutlined,
  PushpinOutlined,
  StarFilled,
  StarOutlined,
} from "@ant-design/icons-vue";
import { ref } from "vue";

import { useOutsidePointerDown } from "@/shared/lib/useOutsidePointerDown";
import UiCard from "@/shared/ui/Card.vue";

type TopicStatus = "open" | "closed" | "archived" | "hidden";
type TopicLifecycleStatus = "open" | "closed";

defineProps<{
  bookmarked: boolean;
  bookmarkCount: number;
  bookmarkPending: boolean;
  topicLiked: boolean;
  topicLikeCount: number;
  topicLikePending: boolean;
  canFlagTopic: boolean;
  flagTopicPending: boolean;
  canManageTopic: boolean;
  topicStatus: TopicStatus;
  topicPinned: boolean;
  lifecyclePending: boolean;
  deleteTopicPending: boolean;
  status: string;
}>();

const emit = defineEmits<{
  toggleBookmark: [];
  toggleTopicLike: [];
  copyLink: [];
  flagTopic: [];
  setTopicStatus: [status: TopicLifecycleStatus];
  toggleTopicPinned: [];
  moveTopic: [];
  deleteTopic: [];
}>();

const toolbarMoreRef = ref<HTMLDetailsElement | null>(null);

useOutsidePointerDown(toolbarMoreRef, closeMoreMenu, () => Boolean(toolbarMoreRef.value?.open));

function closeMoreMenu() {
  if (toolbarMoreRef.value) {
    toolbarMoreRef.value.open = false;
  }
}

function flagTopic() {
  closeMoreMenu();
  emit("flagTopic");
}

function setTopicStatus(status: TopicLifecycleStatus) {
  closeMoreMenu();
  emit("setTopicStatus", status);
}

function toggleTopicPinned() {
  closeMoreMenu();
  emit("toggleTopicPinned");
}

function moveTopic() {
  closeMoreMenu();
  emit("moveTopic");
}

function deleteTopic() {
  closeMoreMenu();
  emit("deleteTopic");
}
</script>

<template>
  <UiCard class="topic-thread-toolbar">
    <div class="toolbar-actions" aria-label="主题操作">
      <button
        class="toolbar-icon-button"
        :class="{ 'is-active': topicLiked }"
        type="button"
        :title="topicLiked ? '取消点赞主题' : '点赞主题'"
        :aria-label="`${topicLiked ? '取消点赞主题' : '点赞主题'}，当前 ${topicLikeCount}`"
        :aria-pressed="topicLiked"
        :disabled="topicLikePending"
        @click="emit('toggleTopicLike')"
      >
        <HeartFilled v-if="topicLiked" aria-hidden="true" />
        <HeartOutlined v-else aria-hidden="true" />
        <span v-if="topicLikeCount" class="toolbar-count">{{ topicLikeCount }}</span>
      </button>
      <button
        class="toolbar-icon-button"
        :class="{ 'is-active': bookmarked }"
        type="button"
        :title="bookmarked ? '取消收藏主题' : '收藏主题'"
        :aria-label="`${bookmarked ? '取消收藏主题' : '收藏主题'}，当前 ${bookmarkCount}`"
        :aria-pressed="bookmarked"
        :disabled="bookmarkPending"
        @click="emit('toggleBookmark')"
      >
        <StarFilled v-if="bookmarked" aria-hidden="true" />
        <StarOutlined v-else aria-hidden="true" />
        <span v-if="bookmarkCount" class="toolbar-count">{{ bookmarkCount }}</span>
      </button>
      <button class="toolbar-icon-button" type="button" title="复制主题链接" aria-label="复制主题链接" @click="emit('copyLink')">
        <LinkOutlined aria-hidden="true" />
      </button>
      <details ref="toolbarMoreRef" class="toolbar-more" @keydown.esc="closeMoreMenu">
        <summary title="更多主题操作" aria-label="更多主题操作">
          <EllipsisOutlined aria-hidden="true" />
        </summary>
        <div class="toolbar-more-menu">
          <button type="button" :disabled="flagTopicPending || !canFlagTopic" @click="flagTopic">
            <FlagOutlined aria-hidden="true" />
            举报
          </button>
          <template v-if="canManageTopic">
            <button
              type="button"
              :disabled="lifecyclePending"
              @click="setTopicStatus(topicStatus === 'open' ? 'closed' : 'open')"
            >
              <CloseCircleOutlined v-if="topicStatus === 'open'" aria-hidden="true" />
              <CheckCircleOutlined v-else aria-hidden="true" />
              {{ topicStatus === "open" ? "关闭" : "打开" }}
            </button>
            <button type="button" :disabled="lifecyclePending" @click="toggleTopicPinned">
              <PushpinOutlined aria-hidden="true" />
              {{ topicPinned ? "取消置顶" : "置顶" }}
            </button>
            <button type="button" :disabled="lifecyclePending" @click="moveTopic">
              <FolderOpenOutlined aria-hidden="true" />
              更换版块
            </button>
            <button type="button" :disabled="deleteTopicPending" @click="deleteTopic">
              <DeleteOutlined aria-hidden="true" />
              {{ deleteTopicPending ? "删除中…" : "删除主题" }}
            </button>
          </template>
        </div>
      </details>
    </div>
    <p v-if="status" class="toolbar-status" role="status">{{ status }}</p>
  </UiCard>
</template>

<style scoped lang="scss" src="./TopicThreadToolbar.scss"></style>
