<script setup lang="ts">
import { CommentOutlined, DownOutlined, UpOutlined } from "@ant-design/icons-vue";
import { computed } from "vue";

import type { PostItemVM } from "@/entities/post/model";
import PostItem from "@/features/posts/components/PostItem.vue";
import UiCard from "@/shared/ui/Card.vue";

const props = defineProps<{
  replies: PostItemVM[];
  expanded: boolean;
  currentUserId?: string | null;
  currentUserRole?: string | null;
  canManageSolution: boolean;
  solutionPending: boolean;
}>();

const emit = defineEmits<{
  toggle: [];
  blockAuthor: [post: PostItemVM];
  quote: [post: PostItemVM];
  requireLogin: [message: string];
  toggleSolution: [post: PostItemVM];
}>();

const replyCountLabel = computed(() => `${props.replies.length} 条回复`);
</script>

<template>
  <section v-if="replies.length" id="replies" class="topic-replies-panel" aria-label="回复列表">
    <UiCard class="topic-replies-toggle" :class="{ 'is-expanded': expanded }">
      <div class="topic-replies-toggle__summary">
        <CommentOutlined aria-hidden="true" />
        <strong>{{ expanded ? replyCountLabel : "回复已收起" }}</strong>
        <span>{{ replyCountLabel }}</span>
      </div>
      <button
        class="topic-replies-toggle__button"
        type="button"
        :aria-expanded="expanded"
        aria-controls="topic-reply-list"
        @click="emit('toggle')"
      >
        {{ expanded ? "收起回复" : `查看 ${replies.length} 条回复` }}
        <UpOutlined v-if="expanded" aria-hidden="true" />
        <DownOutlined v-else aria-hidden="true" />
      </button>
    </UiCard>

    <div v-if="expanded" id="topic-reply-list" class="post-list">
      <div v-for="post in replies" :id="`post-${post.floor}`" :key="post.id" class="post-anchor">
        <PostItem
          :post="post"
          variant="reply"
          :current-user-id="currentUserId"
          :current-user-role="currentUserRole"
          :can-manage-solution="canManageSolution"
          :solution-pending="solutionPending"
          @quote="emit('quote', post)"
          @require-login="emit('requireLogin', $event)"
          @toggle-solution="emit('toggleSolution', post)"
          @block-author="emit('blockAuthor', post)"
        />
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./TopicRepliesPanel.scss"></style>
