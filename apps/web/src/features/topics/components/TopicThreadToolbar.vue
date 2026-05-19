<script setup lang="ts">
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

defineProps<{
  visibleCount: number;
  totalCount: number;
  onlyAuthor: boolean;
  bookmarked: boolean;
  bookmarkCount: number;
  bookmarkPending: boolean;
  canFlagTopic: boolean;
  flagTopicPending: boolean;
  status: string;
}>();

const emit = defineEmits<{
  toggleOnlyAuthor: [];
  toggleBookmark: [];
  copyLink: [];
  flagTopic: [];
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
    <p v-if="status" class="toolbar-status" role="status">{{ status }}</p>
  </UiCard>
</template>

<style scoped lang="scss" src="./TopicThreadToolbar.scss"></style>
