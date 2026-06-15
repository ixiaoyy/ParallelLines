<script setup lang="ts">
import { TagsOutlined } from "@ant-design/icons-vue";
import { computed } from "vue";

import type { BoardSummary } from "@/entities/board/model";
import { sortBoardsWithFeedbackLast } from "@/entities/board/order";
import type { TagItemVM } from "@/features/tags/model";
import { boardToneClass } from "@/shared/theme/boardPalette";

const props = defineProps<{
  boards: BoardSummary[];
  tags: TagItemVM[];
  boardsLoading: boolean;
  boardsError: boolean;
  tagsLoading: boolean;
  tagsError: boolean;
}>();

const publicBoards = computed(() =>
  sortBoardsWithFeedbackLast(props.boards.filter((board) => board.visibility === "public")),
);
const visibleTags = computed(() => props.tags.slice(0, 12));
</script>

<template>
  <nav class="home-mobile-discovery" aria-label="移动端版块与标签导航">
    <div class="mobile-discovery__topline">
      <RouterLink class="mobile-discovery__publish" :to="{ name: 'new-topic' }">发布主题</RouterLink>
      <RouterLink class="mobile-discovery__all" :to="{ name: 'board-directory' }">全部版块</RouterLink>
    </div>

    <section class="mobile-discovery__section" aria-labelledby="mobile-discovery-boards-title">
      <h2 id="mobile-discovery-boards-title">版块</h2>
      <p v-if="boardsLoading" class="mobile-discovery__state" role="status">正在加载版块…</p>
      <p v-else-if="boardsError" class="mobile-discovery__state mobile-discovery__state--error">版块暂时不可用</p>
      <div v-else class="mobile-discovery__scroller">
        <RouterLink
          v-for="board in publicBoards"
          :key="board.id"
          class="mobile-board-chip"
          :class="boardToneClass(board.slug)"
          :to="{ name: 'board-detail', params: { slug: board.slug } }"
        >
          <span aria-hidden="true"></span>
          {{ board.name }}
        </RouterLink>
      </div>
    </section>

    <section class="mobile-discovery__section" aria-labelledby="mobile-discovery-tags-title">
      <h2 id="mobile-discovery-tags-title">标签</h2>
      <p v-if="tagsLoading" class="mobile-discovery__state" role="status">正在加载标签…</p>
      <p v-else-if="tagsError" class="mobile-discovery__state mobile-discovery__state--error">标签暂时不可用</p>
      <div v-else class="mobile-discovery__scroller">
        <RouterLink
          v-for="tag in visibleTags"
          :key="tag.id"
          class="mobile-tag-chip"
          :to="{ name: 'search', query: { q: tag.name, tag: tag.name } }"
        >
          <TagsOutlined aria-hidden="true" />
          {{ tag.name }}
        </RouterLink>
        <RouterLink class="mobile-tag-chip mobile-tag-chip--all" :to="{ name: 'search' }">所有标签</RouterLink>
      </div>
    </section>
  </nav>
</template>

<style scoped lang="scss" src="./HomeMobileDiscovery.scss"></style>
