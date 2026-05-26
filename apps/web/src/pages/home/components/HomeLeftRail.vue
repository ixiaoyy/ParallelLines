<script setup lang="ts">
import { computed } from "vue";

import type { BoardSummary } from "@/entities/board/model";
import type { TagItemVM } from "@/features/tags/model";
import { compactNumber } from "@/shared/lib/format";
import { boardToneClass, tagToneClass } from "@/shared/theme/boardPalette";

const props = defineProps<{
  boards: BoardSummary[];
  tags: TagItemVM[];
  boardsLoading: boolean;
  boardsError: boolean;
  tagsLoading: boolean;
  tagsError: boolean;
}>();

const publicBoards = computed(() => props.boards.filter((board) => board.visibility === "public"));
const privateBoards = computed(() => props.boards.filter((board) => board.visibility !== "public"));
</script>

<template>
  <aside class="home-left-rail" aria-label="论坛导航">
    <RouterLink class="rail-action" :to="{ name: 'new-topic' }">新建主题</RouterLink>

    <section class="rail-section" aria-labelledby="rail-boards-title">
      <h2 id="rail-boards-title">版块</h2>
      <p v-if="boardsLoading" class="rail-state">正在加载版块…</p>
      <p v-else-if="boardsError" class="rail-state rail-state--error">版块暂时不可用</p>
      <template v-else>
        <p v-if="!publicBoards.length && !privateBoards.length" class="rail-state">暂无可见版块</p>
        <h3 v-if="publicBoards.length" class="rail-subtitle">公共版块</h3>
        <RouterLink
          v-for="board in publicBoards"
          :key="board.id"
          class="rail-board"
          :class="boardToneClass(board.slug)"
          :to="{ name: 'board-detail', params: { slug: board.slug } }"
        >
          <span class="rail-board-mark tone-mark-square" aria-hidden="true"></span>
          <span class="rail-board-copy">
            <strong>{{ board.name }}</strong>
            <small>{{ board.description }}</small>
          </span>
          <em>{{ compactNumber(board.topicCount) }}</em>
        </RouterLink>
        <h3 v-if="privateBoards.length" class="rail-subtitle">邀请版块</h3>
        <RouterLink
          v-for="board in privateBoards"
          :key="board.id"
          class="rail-board rail-board--private"
          :class="boardToneClass(board.slug)"
          :to="{ name: 'board-detail', params: { slug: board.slug } }"
        >
          <span class="rail-board-mark tone-mark-square" aria-hidden="true"></span>
          <span class="rail-board-copy">
            <strong>{{ board.name }}</strong>
            <small>{{ board.description }}</small>
          </span>
          <em>{{ compactNumber(board.topicCount) }}</em>
        </RouterLink>
      </template>
    </section>

    <section class="rail-section rail-section--tags" aria-labelledby="rail-tags-title">
      <h2 id="rail-tags-title">标签</h2>
      <p v-if="tagsLoading" class="rail-state">正在加载标签…</p>
      <p v-else-if="tagsError" class="rail-state rail-state--error">标签暂时不可用</p>
      <template v-else>
        <RouterLink
          v-for="tag in tags.slice(0, 6)"
          :key="tag.id"
          class="rail-tag tone-chip"
          :class="tagToneClass(tag.name)"
          :to="{ name: 'search', query: { q: tag.name, tag: tag.name } }"
        >
          #{{ tag.name }}
        </RouterLink>
      </template>
    </section>
  </aside>
</template>

<style scoped lang="scss" src="./HomeLeftRail.scss"></style>
