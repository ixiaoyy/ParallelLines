<script setup lang="ts">
import type { NotificationLevel } from "@/features/notifications/model";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

type TopicStatus = "open" | "closed" | "archived" | "hidden";
type TopicLifecycleStatus = "open" | "closed" | "archived";

const notificationOptions: Array<{ value: NotificationLevel; label: string; helper: string }> = [
  { value: "watching", label: "关注", helper: "所有新楼层通知" },
  { value: "tracking", label: "跟踪", helper: "重要更新通知" },
  { value: "normal", label: "普通", helper: "只收回复/提及" },
  { value: "muted", label: "静音", helper: "不接收主题通知" },
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
  splitTopic: [];
  mergeTopic: [];
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
      <span class="panel-kicker">楼层流</span>
      <strong>{{ visibleCount }} / {{ totalCount }} 个可见楼层</strong>
    </div>
    <div class="toolbar-actions" aria-label="主题操作">
      <UiButton tone="ghost" :aria-pressed="onlyAuthor" @click="emit('toggleOnlyAuthor')">
        {{ onlyAuthor ? "显示全部" : "只看楼主" }}
      </UiButton>
      <UiButton tone="ghost" :aria-pressed="qaSort" @click="emit('toggleQaSort')">
        {{ qaSort ? "按时间排序" : "问答排序" }}
      </UiButton>
      <UiButton
        :tone="topicLiked ? 'success' : 'subtle'"
        :aria-pressed="topicLiked"
        :disabled="topicLikePending"
        @click="emit('toggleTopicLike')"
      >
        {{ topicLiked ? "已点赞" : "点赞主题" }}
        <span v-if="topicLikeCount">· {{ topicLikeCount }}</span>
      </UiButton>
      <UiButton
        :tone="bookmarked ? 'success' : 'subtle'"
        :aria-pressed="bookmarked"
        :disabled="bookmarkPending"
        @click="emit('toggleBookmark')"
      >
        {{ bookmarked ? "已收藏" : "收藏主题" }}
        <span v-if="bookmarkCount">· {{ bookmarkCount }}</span>
      </UiButton>
      <div class="topic-score-vote" aria-label="主题赞成反对投票">
        <UiButton
          :tone="topicVoteValue === 1 ? 'success' : 'ghost'"
          :aria-pressed="topicVoteValue === 1"
          :disabled="topicVotePending"
          @click="emit('voteTopic', topicVoteValue === 1 ? 0 : 1)"
        >
          赞成
        </UiButton>
        <strong>{{ topicVoteScore }}</strong>
        <UiButton
          :tone="topicVoteValue === -1 ? 'danger' : 'ghost'"
          :aria-pressed="topicVoteValue === -1"
          :disabled="topicVotePending"
          @click="emit('voteTopic', topicVoteValue === -1 ? 0 : -1)"
        >
          反对
        </UiButton>
        <span>{{ topicVoteCount }} 票</span>
      </div>
      <UiButton tone="subtle" @click="emit('copyLink')">复制链接</UiButton>
      <UiButton tone="subtle" @click="emit('openInvites')">邀请成员</UiButton>
      <UiButton tone="ghost" :disabled="flagTopicPending || !canFlagTopic" @click="emit('flagTopic')">
        举报主题
      </UiButton>
    </div>
    <label class="notification-control">
      <span>主题通知</span>
      <select
        :value="notificationLevel"
        :disabled="notificationPending || !canSetNotification"
        aria-label="设置主题通知级别"
        @change="onNotificationChange"
      >
        <option v-for="option in notificationOptions" :key="option.value" :value="option.value">
          {{ option.label }} · {{ option.helper }}
        </option>
      </select>
    </label>
    <div v-if="canManageTopic" class="lifecycle-actions" aria-label="版主主题管理">
      <UiButton
        tone="subtle"
        :disabled="lifecyclePending"
        @click="emit('setTopicStatus', topicStatus === 'open' ? 'closed' : 'open')"
      >
        {{ topicStatus === "open" ? "关闭主题" : "重新打开" }}
      </UiButton>
      <UiButton tone="subtle" :disabled="lifecyclePending" @click="emit('setTopicStatus', 'archived')">
        归档
      </UiButton>
      <UiButton tone="subtle" :disabled="lifecyclePending" @click="emit('toggleTopicPinned')">
        {{ topicPinned ? "取消置顶" : "置顶" }}
      </UiButton>
      <UiButton tone="subtle" :disabled="lifecyclePending" @click="emit('moveTopic')">移动</UiButton>
      <UiButton tone="subtle" :disabled="lifecyclePending" @click="emit('splitTopic')">拆分</UiButton>
      <UiButton tone="subtle" :disabled="lifecyclePending" @click="emit('mergeTopic')">合并</UiButton>
    </div>
    <p v-if="status" class="toolbar-status" role="status">{{ status }}</p>
  </UiCard>
</template>

<style scoped lang="scss" src="./TopicThreadToolbar.scss"></style>
