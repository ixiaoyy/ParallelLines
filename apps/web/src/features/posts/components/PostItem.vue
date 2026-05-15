<script setup lang="ts">
import { computed } from "vue";

import type { PostItemVM } from "@/entities/post/model";
import { setPostLike } from "@/features/interactions/api";
import { useOptimisticToggle } from "@/features/interactions/useOptimisticToggle";
import { useCreateFlag } from "@/features/moderation/queries";
import { hasAccessToken } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const props = defineProps<{ post: PostItemVM }>();

const hasCodeBlock = computed(() => props.post.cookedHtml.includes("<pre"));
const canFlag = computed(() => hasAccessToken() && !props.post.deleted);
const flagPostMutation = useCreateFlag();
const flagPending = computed(() => flagPostMutation.isPending.value);
const {
  active: liked,
  count: optimisticLikeCount,
  pending: likePending,
  toggle: toggleLike,
} = useOptimisticToggle({
  active: () => false,
  count: () => props.post.likeCount,
  enabled: hasAccessToken,
  commit: (active) => setPostLike(props.post.id, active),
  readActive: (response) => response.active,
  readCount: (response) => response.count,
});

function flagPost() {
  if (!canFlag.value) {
    return;
  }

  flagPostMutation.mutate({
    target_type: "post",
    target_id: props.post.id,
    reason: "other",
    detail: "用户从楼层操作发起举报。",
  });
}
</script>

<template>
  <UiCard class="post-item" :class="{ deleted: post.deleted }">
    <aside class="post-author">
      <UiAvatar :name="post.authorName" />
      <strong>{{ post.authorName }}</strong>
      <span>#{{ post.floor }}</span>
    </aside>
    <article class="post-body">
      <time>{{ relativeTime(post.createdAt) }}</time>
      <div v-if="post.deleted" class="deleted-copy">该楼层已被版主隐藏。</div>
      <div v-else class="markdown-body" v-html="post.cookedHtml" />
      <footer>
        <UiButton
          :tone="liked ? 'success' : 'ghost'"
          :aria-pressed="liked"
          :disabled="likePending"
          @click="toggleLike"
        >
          {{ liked ? "已赞" : "赞" }} {{ optimisticLikeCount }}
        </UiButton>
        <UiButton tone="ghost">回复 {{ post.replyCount }}</UiButton>
        <UiButton v-if="hasCodeBlock" tone="subtle" aria-label="复制本楼层代码块">复制代码</UiButton>
        <UiButton tone="ghost" :disabled="flagPending || !canFlag" @click="flagPost">举报</UiButton>
        <UiButton tone="ghost">引用</UiButton>
      </footer>
    </article>
  </UiCard>
</template>

<style scoped lang="scss" src="./PostItem.scss"></style>
