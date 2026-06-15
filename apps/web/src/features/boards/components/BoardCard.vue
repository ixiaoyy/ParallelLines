<script setup lang="ts">
import type { BoardSummary } from "@/entities/board/model";
import { compactNumber } from "@/shared/lib/format";
import { boardToneClass } from "@/shared/theme/boardPalette";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

defineProps<{ board: BoardSummary }>();
defineEmits<{ toggleFollow: [slug: string] }>();
</script>

<template>
  <UiCard class="board-card" :class="boardToneClass(board.slug)">
    <div class="board-mark tone-mark-square" :title="board.name">
      {{ board.name.slice(0, 1) }}
    </div>
    <div class="board-body">
      <div class="board-heading">
        <h3>{{ board.name }}</h3>
        <UiBadge :tone="board.isFollowing ? 'green' : 'blue'">
          {{ board.isFollowing ? "已关注" : "开放版块" }}
        </UiBadge>
      </div>
      <p>{{ board.description }}</p>
      <dl>
        <div>
          <dt>主题</dt>
          <dd>{{ compactNumber(board.topicCount) }}</dd>
        </div>
        <div>
          <dt>回复</dt>
          <dd>{{ compactNumber(board.postCount) }}</dd>
        </div>
        <div>
          <dt>关注</dt>
          <dd>{{ compactNumber(board.followerCount) }}</dd>
        </div>
      </dl>
    </div>
    <UiButton :tone="board.isFollowing ? 'subtle' : 'primary'" @click="$emit('toggleFollow', board.slug)">
      {{ board.isFollowing ? "调整通知" : "关注" }}
    </UiButton>
  </UiCard>
</template>

<style scoped>
.board-card {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 1rem;
  align-items: start;
  padding: 1rem;
}

.board-mark {
  display: grid;
  width: 3.4rem;
  height: 3.4rem;
  place-items: center;
  border: 1px solid var(--board-mark-border);
  border-radius: 1.15rem;
  color: var(--board-mark-fg);
  background: var(--board-mark-bg);
  font-size: 1.35rem;
  font-weight: 900;
}

.board-heading {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

h3,
p,
dl {
  margin: 0;
}

h3 {
  color: var(--title);
}

p {
  margin-top: 0.35rem;
  line-height: 1.65;
}

dl {
  display: flex;
  gap: 1.25rem;
  margin-top: 0.9rem;
}

dt {
  color: var(--muted);
  font-size: 0.75rem;
}

dd {
  margin: 0.12rem 0 0;
  color: var(--title);
  font-weight: 800;
}

@media (max-width: 720px) {
  .board-card {
    grid-template-columns: auto 1fr;
  }

  .board-card :deep(.ui-button) {
    grid-column: 1 / -1;
  }
}
</style>
