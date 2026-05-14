<script setup lang="ts">
import type { PostItemVM } from "@/entities/post/model";
import { relativeTime } from "@/shared/lib/format";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

defineProps<{ post: PostItemVM }>();
</script>

<template>
  <UiCard class="post-item" :class="{ deleted: post.deleted }">
    <aside>
      <UiAvatar :name="post.authorName" />
      <strong>{{ post.authorName }}</strong>
      <span>#{{ post.floor }}</span>
    </aside>
    <article>
      <time>{{ relativeTime(post.createdAt) }}</time>
      <div v-if="post.deleted" class="deleted-copy">该楼层已被版主隐藏。</div>
      <div v-else class="markdown-body" v-html="post.cookedHtml" />
      <footer>
        <UiButton tone="ghost">赞 {{ post.likeCount }}</UiButton>
        <UiButton tone="ghost">回复 {{ post.replyCount }}</UiButton>
      </footer>
    </article>
  </UiCard>
</template>

<style scoped>
.post-item {
  display: grid;
  grid-template-columns: 9rem 1fr;
  gap: 1rem;
  padding: 1rem;
}

aside {
  display: grid;
  align-content: start;
  justify-items: center;
  gap: 0.35rem;
  color: var(--title);
}

aside span,
time {
  color: var(--muted);
  font-size: 0.82rem;
}

article {
  min-width: 0;
}

.deleted {
  opacity: 0.72;
}

.deleted-copy {
  border-radius: 0.85rem;
  padding: 1rem;
  color: var(--muted);
  background: var(--bg-subtle);
}

footer {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

@media (max-width: 680px) {
  .post-item {
    grid-template-columns: 1fr;
  }

  aside {
    grid-template-columns: auto auto 1fr;
    justify-items: start;
  }
}
</style>
