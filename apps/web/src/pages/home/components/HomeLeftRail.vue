<script setup lang="ts">
import {
  BulbOutlined,
  CoffeeOutlined,
  EditOutlined,
  FileTextOutlined,
  FireOutlined,
  FlagOutlined,
  FolderOpenOutlined,
  HeartOutlined,
  LikeOutlined,
  NotificationOutlined,
  QuestionCircleOutlined,
  ReadOutlined,
  TagsOutlined,
  TeamOutlined,
  TrophyOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons-vue";
import type { Component } from "vue";
import { computed } from "vue";

import type { BoardSummary } from "@/entities/board/model";
import type { TagItemVM } from "@/features/tags/model";
import { compactNumber } from "@/shared/lib/format";
import { boardToneClass } from "@/shared/theme/boardPalette";

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

const featuredTagNames = [
  "公告",
  "集中帖",
  "精华神帖",
  "快问快答",
  "人工智能",
  "原创",
  "资源分享",
  "福利羊毛",
  "教程",
  "作品集",
  "读书",
  "健康",
  "闲聊",
  "站务反馈",
  "活动",
  "发帖模板",
];

const tagIcons: Record<string, Component> = {
  公告: NotificationOutlined,
  集中帖: TeamOutlined,
  精华神帖: LikeOutlined,
  快问快答: QuestionCircleOutlined,
  人工智能: BulbOutlined,
  原创: EditOutlined,
  资源分享: FolderOpenOutlined,
  福利羊毛: FireOutlined,
  教程: FileTextOutlined,
  作品集: TrophyOutlined,
  读书: ReadOutlined,
  健康: HeartOutlined,
  闲聊: CoffeeOutlined,
  站务反馈: FlagOutlined,
  活动: FireOutlined,
  发帖模板: TagsOutlined,
};

const tagAccentColors: Record<string, string> = {
  公告: "#0ea5e9",
  集中帖: "#06b6d4",
  精华神帖: "#2563eb",
  快问快答: "#65a30d",
  人工智能: "#8b5cf6",
  原创: "#0ea5e9",
  资源分享: "#ea580c",
  福利羊毛: "#f59e0b",
  教程: "#6366f1",
  作品集: "#db2777",
  读书: "#be185d",
  健康: "#10b981",
  闲聊: "#64748b",
  站务反馈: "#475569",
  活动: "#f59e0b",
  发帖模板: "#14b8a6",
};

const featuredTags = computed(() => {
  const byName = new Map(props.tags.map((tag) => [tag.name, tag]));
  return featuredTagNames.flatMap((name) => {
    const tag = byName.get(name);
    return tag ? [tag] : [];
  });
});

function tagIcon(tagName: string): Component {
  return tagIcons[tagName] ?? TagsOutlined;
}

function tagAccentStyle(tagName: string): Record<string, string> {
  return { "--tag-accent": tagAccentColors[tagName] ?? "#409eff" };
}
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
        <div class="rail-tag-list">
          <RouterLink
            v-for="tag in featuredTags"
            :key="tag.id"
            class="rail-tag"
            :style="tagAccentStyle(tag.name)"
            :to="{ name: 'search', query: { q: tag.name, tag: tag.name } }"
          >
            <component :is="tagIcon(tag.name)" aria-hidden="true" />
            <span>{{ tag.name }}</span>
            <i v-if="tag.topicCount > 0" aria-hidden="true"></i>
          </RouterLink>
          <RouterLink class="rail-tag rail-tag--all" :to="{ name: 'search' }">
            <UnorderedListOutlined aria-hidden="true" />
            <span>所有标签</span>
          </RouterLink>
        </div>
      </template>
    </section>
  </aside>
</template>

<style scoped lang="scss" src="./HomeLeftRail.scss"></style>
