<script setup lang="ts">
import type { BoardSummary } from "@/entities/board/model";
import { compactNumber } from "@/shared/lib/format";

defineProps<{
  boards: BoardSummary[];
  loading: boolean;
  error: boolean;
}>();
</script>

<template>
  <section class="home-category-grid" aria-label="推荐分类">
    <p v-if="loading" class="panel-state" role="status">正在加载分类…</p>
    <p v-else-if="error" class="panel-state panel-state--error" role="alert">分类暂时不可用</p>
    <template v-else>
      <RouterLink
        v-for="board in boards"
        :key="board.id"
        class="category"
        :to="{ name: 'board-detail', params: { slug: board.slug } }"
        :style="{ '--board-color': board.color }"
      >
        <h3>{{ board.name }}</h3>
        <p>{{ board.description }}</p>
        <div class="category-meta">
          <span>{{ compactNumber(board.topicCount) }} 个主题</span>
          <span>{{ compactNumber(board.postCount) }} 个帖子</span>
        </div>
      </RouterLink>
    </template>
  </section>
</template>

<style scoped lang="scss" src="./HomeCategoryGrid.scss"></style>
