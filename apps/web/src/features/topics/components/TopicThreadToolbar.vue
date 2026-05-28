<script setup lang="ts">
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  BellOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CommentOutlined,
  DeleteOutlined,
  EllipsisOutlined,
  FlagOutlined,
  FolderOpenOutlined,
  HeartFilled,
  HeartOutlined,
  LinkOutlined,
  PushpinOutlined,
  RocketOutlined,
  StarFilled,
  StarOutlined,
  UserOutlined,
  UserAddOutlined,
} from "@ant-design/icons-vue";

import type { NotificationLevel } from "@/features/notifications/model";
import UiCard from "@/shared/ui/Card.vue";

type TopicStatus = "open" | "closed" | "archived" | "hidden";
type TopicLifecycleStatus = "open" | "closed";

const notificationOptions: Array<{ value: NotificationLevel; label: string }> = [
  { value: "watching", label: "关注" },
  { value: "tracking", label: "跟踪" },
  { value: "normal", label: "普通" },
  { value: "muted", label: "静音" },
];

defineProps<{
  visibleCount: number;
  totalCount: number;
  onlyAuthor: boolean;
  qaSort: boolean;
  bookmarked: boolean;
  bookmarkCount: number;
  bookmarkPending: boolean;
  topicLiked: boolean;
  topicLikeCount: number;
  topicLikePending: boolean;
  topicVoteScore: number;
  topicVoteCount: number;
  topicVoteValue: number;
  topicVotePending: boolean;
  canFlagTopic: boolean;
  flagTopicPending: boolean;
  canManageTopic: boolean;
  topicStatus: TopicStatus;
  topicPinned: boolean;
  lifecyclePending: boolean;
  deleteTopicPending: boolean;
  notificationLevel: NotificationLevel;
  notificationPending: boolean;
  canSetNotification: boolean;
  status: string;
}>();

const emit = defineEmits<{
  toggleOnlyAuthor: [];
  toggleQaSort: [];
  toggleBookmark: [];
  toggleTopicLike: [];
  copyLink: [];
  openInvites: [];
  flagTopic: [];
  setTopicStatus: [status: TopicLifecycleStatus];
  toggleTopicPinned: [];
  moveTopic: [];
  deleteTopic: [];
  setNotificationLevel: [level: NotificationLevel];
  voteTopic: [value: -1 | 0 | 1];
}>();

function onNotificationChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  emit("setNotificationLevel", target.value as NotificationLevel);
}
</script>

<template>
  <UiCard class="topic-thread-toolbar">
    <div class="toolbar-summary">
      <CommentOutlined aria-hidden="true" />
      <strong>{{ visibleCount }}/{{ totalCount }} 楼</strong>
    </div>
    <div class="toolbar-actions" aria-label="主题操作">
      <button
        class="toolbar-icon-button"
        :class="{ 'is-active': onlyAuthor }"
        type="button"
        :title="onlyAuthor ? '显示全部楼层' : '只看楼主'"
        :aria-label="onlyAuthor ? '显示全部楼层' : '只看楼主'"
        :aria-pressed="onlyAuthor"
        @click="emit('toggleOnlyAuthor')"
      >
        <UserOutlined aria-hidden="true" />
      </button>
      <button
        class="toolbar-icon-button"
        :class="{ 'is-active': qaSort }"
        type="button"
        :title="qaSort ? '按时间排序' : '问答排序'"
        :aria-label="qaSort ? '按时间排序' : '问答排序'"
        :aria-pressed="qaSort"
        @click="emit('toggleQaSort')"
      >
        <RocketOutlined aria-hidden="true" />
      </button>
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
      <div class="topic-vote-strip" aria-label="主题赞成反对投票">
        <button
          class="toolbar-icon-button toolbar-icon-button--vote"
          :class="{ 'is-active': topicVoteValue === 1 }"
          type="button"
          title="赞成主题"
          aria-label="赞成主题"
          :aria-pressed="topicVoteValue === 1"
          :disabled="topicVotePending"
          @click="emit('voteTopic', topicVoteValue === 1 ? 0 : 1)"
        >
          <ArrowUpOutlined aria-hidden="true" />
        </button>
        <strong>{{ topicVoteScore }}</strong>
        <button
          class="toolbar-icon-button toolbar-icon-button--vote"
          :class="{ 'is-danger-active': topicVoteValue === -1 }"
          type="button"
          title="反对主题"
          aria-label="反对主题"
          :aria-pressed="topicVoteValue === -1"
          :disabled="topicVotePending"
          @click="emit('voteTopic', topicVoteValue === -1 ? 0 : -1)"
        >
          <ArrowDownOutlined aria-hidden="true" />
        </button>
        <span v-if="topicVoteCount">{{ topicVoteCount }}</span>
      </div>
      <button class="toolbar-icon-button" type="button" title="邀请成员" aria-label="邀请成员" @click="emit('openInvites')">
        <UserAddOutlined aria-hidden="true" />
      </button>
      <label class="notification-control" title="主题通知">
        <BellOutlined aria-hidden="true" />
        <select
          :value="notificationLevel"
          :disabled="notificationPending || !canSetNotification"
          aria-label="设置主题通知级别"
          @change="onNotificationChange"
        >
          <option v-for="option in notificationOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <details class="toolbar-more">
        <summary title="更多主题操作" aria-label="更多主题操作">
          <EllipsisOutlined aria-hidden="true" />
        </summary>
        <div class="toolbar-more-menu">
          <button type="button" :disabled="flagTopicPending || !canFlagTopic" @click="emit('flagTopic')">
            <FlagOutlined aria-hidden="true" />
            举报
          </button>
          <template v-if="canManageTopic">
            <button
              type="button"
              :disabled="lifecyclePending"
              @click="emit('setTopicStatus', topicStatus === 'open' ? 'closed' : 'open')"
            >
              <CloseCircleOutlined v-if="topicStatus === 'open'" aria-hidden="true" />
              <CheckCircleOutlined v-else aria-hidden="true" />
              {{ topicStatus === "open" ? "关闭" : "打开" }}
            </button>
            <button type="button" :disabled="lifecyclePending" @click="emit('toggleTopicPinned')">
              <PushpinOutlined aria-hidden="true" />
              {{ topicPinned ? "取消置顶" : "置顶" }}
            </button>
            <button type="button" :disabled="lifecyclePending" @click="emit('moveTopic')">
              <FolderOpenOutlined aria-hidden="true" />
              移动
            </button>
            <button type="button" :disabled="deleteTopicPending" @click="emit('deleteTopic')">
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
