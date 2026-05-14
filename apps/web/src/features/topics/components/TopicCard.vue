<script setup lang="ts">
import type { TopicCardVM } from "@/entities/topic/model";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiBadge from "@/shared/ui/Badge.vue";
import UiCard from "@/shared/ui/Card.vue";

defineProps<{ topic: TopicCardVM }>();
</script>

<template>
  <UiCard class="topic-card">
    <div class="topic-main">
      <div class="topic-meta">
        <UiBadge v-if="topic.pinned" tone="amber">置顶</UiBadge>
        <UiBadge v-if="topic.featured" tone="green">精华</UiBadge>
        <span>{{ topic.boardName }}</span>
        <span>·</span>
        <span>{{ relativeTime(topic.lastPostedAt) }}</span>
      </div>
      <h2>{{ topic.title }}</h2>
      <p>{{ topic.excerpt }}</p>
      <div class="topic-tags">
        <span v-for="tag in topic.tags" :key="tag">#{{ tag }}</span>
      </div>
    </div>

    <div class="topic-side">
      <UiAvatar :name="topic.authorName" />
      <strong>{{ topic.authorName }}</strong>
      <dl>
        <div>
          <dt>回复</dt>
          <dd>{{ compactNumber(topic.replyCount) }}</dd>
        </div>
        <div>
          <dt>浏览</dt>
          <dd>{{ compactNumber(topic.viewCount) }}</dd>
        </div>
        <div>
          <dt>热度</dt>
          <dd>{{ Math.round(topic.hotScore) }}</dd>
        </div>
      </dl>
    </div>
  </UiCard>
</template>

<style scoped>
.topic-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 11rem;
  gap: 1rem;
  padding: 1.1rem;
}

.topic-meta,
.topic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}

.topic-meta {
  color: var(--muted);
  font-size: 0.86rem;
}

h2 {
  margin: 0.55rem 0 0.35rem;
  color: var(--title);
  font-size: clamp(1.1rem, 2vw, 1.5rem);
  letter-spacing: -0.03em;
}

p {
  margin: 0;
  line-height: 1.7;
}

.topic-tags {
  margin-top: 0.75rem;
}

.topic-tags span {
  color: var(--primary);
  font-weight: 700;
}

.topic-side {
  display: grid;
  justify-items: end;
  color: var(--title);
}

dl {
  display: grid;
  width: 100%;
  grid-template-columns: repeat(3, 1fr);
  margin: 0.75rem 0 0;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border);
  text-align: right;
}

dt {
  color: var(--muted);
  font-size: 0.72rem;
}

dd {
  margin: 0.15rem 0 0;
  font-weight: 850;
}

@media (max-width: 720px) {
  .topic-card {
    grid-template-columns: 1fr;
  }

  .topic-side {
    justify-items: start;
  }
}
</style>
