<script setup lang="ts">
import { AppstoreOutlined, FireOutlined, HomeOutlined, StarFilled } from "@ant-design/icons-vue";

import type { BoardSummary } from "@/entities/board/model";
import type { TagItemVM } from "@/features/tags/model";
import { compactNumber } from "@/shared/lib/format";

defineProps<{
  boards: BoardSummary[];
  tags: TagItemVM[];
  boardsLoading: boolean;
  boardsError: boolean;
  tagsLoading: boolean;
  tagsError: boolean;
}>();
</script>

<template>
  <aside class="home-left-rail" aria-label="论坛导航">
    <RouterLink class="rail-action" :to="{ name: 'new-topic' }">新建主题</RouterLink>

    <nav class="rail-section rail-section--primary" aria-label="首页导航">
      <RouterLink class="rail-link rail-link--home rail-link--active" to="/">
        <span class="rail-icon" aria-hidden="true"><HomeOutlined /></span>
        <strong>主页</strong>
        <i aria-hidden="true"></i>
      </RouterLink>
      <RouterLink class="rail-link rail-link--topics" :to="{ name: 'home', hash: '#hot' }">
        <span class="rail-icon" aria-hidden="true"><FireOutlined /></span>
        <strong>话题</strong>
      </RouterLink>
      <RouterLink class="rail-link rail-link--signal" :to="{ name: 'home', hash: '#solved' }">
        <span class="rail-icon" aria-hidden="true"><StarFilled /></span>
        <strong>高信号</strong>
      </RouterLink>
      <RouterLink class="rail-link rail-link--more" :to="{ name: 'board-directory' }">
        <span class="rail-icon" aria-hidden="true"><AppstoreOutlined /></span>
        <strong>更多</strong>
      </RouterLink>
    </nav>

    <section class="rail-section" aria-labelledby="rail-boards-title">
      <h2 id="rail-boards-title">版块</h2>
      <p v-if="boardsLoading" class="rail-state">正在加载版块…</p>
      <p v-else-if="boardsError" class="rail-state rail-state--error">版块暂时不可用</p>
      <template v-else>
        <RouterLink
          v-for="board in boards"
          :key="board.id"
          class="rail-board"
          :to="{ name: 'board-detail', params: { slug: board.slug } }"
          :style="{ '--board-color': board.color }"
        >
          <span class="rail-board-mark" aria-hidden="true"></span>
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
          v-for="(tag, tagIndex) in tags.slice(0, 6)"
          :key="tag.id"
          class="rail-tag"
          :class="`rail-tag--tone-${(tagIndex % 6) + 1}`"
          :to="{ name: 'search', query: { q: tag.name, tag: tag.name } }"
        >
          #{{ tag.name }}
        </RouterLink>
      </template>
    </section>
  </aside>
</template>

<style scoped lang="scss" src="./HomeLeftRail.scss"></style>
