<script setup lang="ts">
import { computed } from "vue";

import type { PostItemVM } from "@/entities/post/model";
import { relativeTime } from "@/shared/lib/format";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const props = defineProps<{ post: PostItemVM }>();

const hasCodeBlock = computed(() => props.post.cookedHtml.includes("<pre"));
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
        <UiButton tone="ghost">赞 {{ post.likeCount }}</UiButton>
        <UiButton tone="ghost">回复 {{ post.replyCount }}</UiButton>
        <UiButton v-if="hasCodeBlock" tone="subtle" aria-label="复制本楼层代码块">复制代码</UiButton>
        <UiButton tone="ghost">引用</UiButton>
      </footer>
    </article>
  </UiCard>
</template>

<style scoped lang="scss" src="./PostItem.scss"></style>
