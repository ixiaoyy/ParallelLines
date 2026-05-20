<script setup lang="ts">
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

type TopicStatus = "open" | "closed" | "archived" | "hidden";
type TopicLifecycleStatus = "open" | "closed" | "archived";

defineProps<{
  visibleCount: number;
  totalCount: number;
  onlyAuthor: boolean;
  bookmarked: boolean;
  bookmarkCount: number;
  bookmarkPending: boolean;
  canFlagTopic: boolean;
  flagTopicPending: boolean;
  canManageTopic: boolean;
  topicStatus: TopicStatus;
  topicPinned: boolean;
  lifecyclePending: boolean;
  status: string;
}>();

const emit = defineEmits<{
  toggleOnlyAuthor: [];
  toggleBookmark: [];
  copyLink: [];
  flagTopic: [];
  setTopicStatus: [status: TopicLifecycleStatus];
  toggleTopicPinned: [];
  moveTopic: [];
  splitTopic: [];
  mergeTopic: [];
}>();
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
      <UiButton
        :tone="bookmarked ? 'success' : 'subtle'"
        :aria-pressed="bookmarked"
        :disabled="bookmarkPending"
        @click="emit('toggleBookmark')"
      >
        {{ bookmarked ? "已收藏" : "收藏主题" }}
        <span v-if="bookmarkCount">· {{ bookmarkCount }}</span>
      </UiButton>
      <UiButton tone="subtle" @click="emit('copyLink')">复制链接</UiButton>
      <UiButton tone="ghost" :disabled="flagTopicPending || !canFlagTopic" @click="emit('flagTopic')">
        举报主题
      </UiButton>
    </div>
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
