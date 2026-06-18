<script setup lang="ts">
import { CommentOutlined } from "@ant-design/icons-vue";
import { computed } from "vue";

import type { PostItemVM } from "@/entities/post/model";
import PostItem from "@/features/posts/components/PostItem.vue";
import UiCard from "@/shared/ui/Card.vue";

const props = defineProps<{
  replies: PostItemVM[];
  currentUserId?: string | null;
  currentUserRole?: string | null;
  canManageSolution: boolean;
  solutionPending: boolean;
}>();

const emit = defineEmits<{
  blockAuthor: [post: PostItemVM];
  quote: [post: PostItemVM];
  reply: [post: PostItemVM];
  requireLogin: [message: string];
  toggleSolution: [post: PostItemVM];
}>();

const replyCountLabel = computed(() => `${props.replies.length} 条回复`);
</script>

<template>
  <section v-if="replies.length" id="replies" class="topic-replies-panel" aria-label="回复列表">
    <UiCard class="topic-replies-header">
      <div class="topic-replies-header__summary">
        <CommentOutlined aria-hidden="true" />
        <strong>{{ replyCountLabel }}</strong>
      </div>
    </UiCard>

    <div id="topic-reply-list" class="post-list">
      <div v-for="post in replies" :id="`post-${post.floor}`" :key="post.id" class="post-anchor">
        <PostItem
          :post="post"
          variant="reply"
          :current-user-id="currentUserId"
          :current-user-role="currentUserRole"
          :can-manage-solution="canManageSolution"
          :solution-pending="solutionPending"
          @quote="emit('quote', post)"
          @reply="emit('reply', post)"
          @require-login="emit('requireLogin', $event)"
          @toggle-solution="emit('toggleSolution', post)"
          @block-author="emit('blockAuthor', post)"
        />
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./TopicRepliesPanel.scss"></style>
