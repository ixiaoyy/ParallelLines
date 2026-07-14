<script setup lang="ts">
import {
  AppstoreOutlined,
  BulbOutlined,
  CoffeeOutlined,
  CompassOutlined,
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
  RightOutlined,
  SearchOutlined,
  StarFilled,
  TagsOutlined,
  TeamOutlined,
  TrophyOutlined,
  UnorderedListOutlined,
  UpOutlined,
} from "@ant-design/icons-vue";
import type { Component } from "vue";
import { computed, ref } from "vue";

import type { BoardSummary } from "@/entities/board/model";
import { sortBoardsWithFeedbackLast } from "@/entities/board/order";
import { useBoards } from "@/features/boards/queries";
import { useTags } from "@/features/tags/queries";
import { compactNumber } from "@/shared/lib/format";
import { boardToneClass } from "@/shared/theme/boardPalette";

const searchQuery = ref("");
const showAllRecommendedBoards = ref(false);
const showAllBoards = ref(false);
const showAllTags = ref(false);
const boardsQuery = useBoards();
const tagsQuery = useTags(60);

const RECOMMENDED_BOARD_LIMIT = 4;
const featuredBoardSlugs = ["qna", "resources", "frontier", "sports", "news", "experience", "dev"];
const featuredTagNames = [
  "AI 科技",
  "社会热点",
  "快问快答",
  "教程",
  "资源分享",
  "精华神帖",
  "原创",
  "健康",
  "闲聊",
  "公告",
  "集中帖",
  "福利羊毛",
  "作品集",
  "读书",
  "站务反馈",
  "活动",
  "发帖模板",
];
const boardIcons: Record<string, Component> = {
  announcements: NotificationOutlined,
  resources: FolderOpenOutlined,
  benefits: FireOutlined,
  reading: ReadOutlined,
  health: HeartOutlined,
  sports: TrophyOutlined,
  news: BulbOutlined,
  frontier: BulbOutlined,
  experience: TrophyOutlined,
  dev: FileTextOutlined,
  engineering: FileTextOutlined,
  qna: QuestionCircleOutlined,
  questions: QuestionCircleOutlined,
  support: QuestionCircleOutlined,
  feedback: FlagOutlined,
  lounge: CoffeeOutlined,
  community: TeamOutlined,
};
const tagIcons: Record<string, Component> = {
  公告: NotificationOutlined,
  集中帖: TeamOutlined,
  精华神帖: LikeOutlined,
  快问快答: QuestionCircleOutlined,
  "AI 科技": BulbOutlined,
  社会热点: FireOutlined,
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
  "AI 科技": "#8b5cf6",
  社会热点: "#ef4444",
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

const normalizedSearch = computed(() => normalizeSearch(searchQuery.value));
const boardItems = computed(() =>
  sortBoardsWithFeedbackLast(
    boardsQuery.data.value ?? [],
    (left, right) => right.topicCount + right.postCount - (left.topicCount + left.postCount),
  ),
);
const publicBoards = computed(() => boardItems.value.filter((board) => board.visibility === "public"));
const filteredBoards = computed(() => {
  const keyword = normalizedSearch.value;
  const boards = boardItems.value;
  if (!keyword) {
    return boards;
  }

  return boards.filter((board) =>
    normalizeSearch(`${board.name} ${board.description} ${board.slug} ${board.parentBoardName ?? ""}`).includes(keyword),
  );
});
const recommendedBoardCandidates = computed(() => {
  const pool = normalizedSearch.value ? filteredBoards.value : publicBoards.value;
  const bySlug = new Map(pool.map((board) => [board.slug, board]));
  const featured = featuredBoardSlugs.flatMap((slug) => {
    const board = bySlug.get(slug);
    return board ? [board] : [];
  });
  const fallbackLimit = Math.max(RECOMMENDED_BOARD_LIMIT - featured.length, 0);
  const fallback = pool.filter((board) => !featured.includes(board)).slice(0, fallbackLimit);
  return [...featured, ...fallback];
});
const recommendedBoards = computed(() => {
  const boards = recommendedBoardCandidates.value;
  if (normalizedSearch.value || showAllRecommendedBoards.value) {
    return boards;
  }

  return boards.slice(0, RECOMMENDED_BOARD_LIMIT);
});
const listedBoards = computed(() => {
  const boards = filteredBoards.value;
  if (normalizedSearch.value || showAllBoards.value) {
    return boards;
  }

  return boards.slice(0, 6);
});
const orderedTags = computed(() => {
  const tags = tagsQuery.data.value ?? [];
  const priority = new Map(featuredTagNames.map((name, index) => [name, index]));
  return [...tags].sort((left, right) => {
    const leftPriority = priority.get(left.name);
    const rightPriority = priority.get(right.name);
    if (leftPriority !== undefined || rightPriority !== undefined) {
      return (leftPriority ?? Number.MAX_SAFE_INTEGER) - (rightPriority ?? Number.MAX_SAFE_INTEGER);
    }

    return right.topicCount - left.topicCount;
  });
});
const filteredTags = computed(() => {
  const keyword = normalizedSearch.value;
  const tags = orderedTags.value;
  if (!keyword) {
    return tags;
  }

  return tags.filter((tag) => normalizeSearch(`${tag.name} ${tag.slug}`).includes(keyword));
});
const listedTags = computed(() => {
  const tags = filteredTags.value;
  if (normalizedSearch.value || showAllTags.value) {
    return tags;
  }

  return tags.slice(0, 8);
});
const hasSearch = computed(() => Boolean(normalizedSearch.value));
const hasExpandableRecommendedBoards = computed(
  () => !hasSearch.value && recommendedBoardCandidates.value.length > RECOMMENDED_BOARD_LIMIT,
);
const hasHiddenBoards = computed(() => !hasSearch.value && filteredBoards.value.length > listedBoards.value.length);
const hasHiddenTags = computed(() => !hasSearch.value && filteredTags.value.length > listedTags.value.length);
const hasVisibleResults = computed(() =>
  recommendedBoards.value.length > 0 || listedBoards.value.length > 0 || listedTags.value.length > 0,
);

// normalizeSearch 用途：统一目录搜索文本的空白与大小写；参数为任意输入文本，返回规整后的字符串且无副作用。
function normalizeSearch(value: string) {
  return value.trim().toLocaleLowerCase();
}

// boardIcon 用途：为版块入口选择与产品导航一致的图标；参数为版块摘要，返回 Vue 图标组件且无副作用。
function boardIcon(board: BoardSummary): Component {
  return boardIcons[board.slug] ?? TagsOutlined;
}

// tagIcon 用途：为标签入口选择与产品导航一致的图标；参数为标签名，返回 Vue 图标组件且无副作用。
function tagIcon(tagName: string): Component {
  return tagIcons[tagName] ?? TagsOutlined;
}

// tagAccentStyle 用途：把标签强调色写入 CSS 变量；参数为标签名，返回样式对象且无副作用。
function tagAccentStyle(tagName: string): Record<string, string> {
  return { "--tag-accent": tagAccentColors[tagName] ?? "var(--primary)" };
}

// boardPurpose 用途：生成推荐版块卡片中的短定位；参数为版块摘要，返回短文本且无副作用。
function boardPurpose(board: BoardSummary) {
  const labels: Record<string, string> = {
    qna: "快速提问与问题排查",
    questions: "快速提问与问题排查",
    support: "快速提问与问题排查",
    resources: "工具、资料与学习路径",
    frontier: "AI 科技与社会热点",
    sports: "赛事新闻与体坛动态",
    news: "AI 科技与社会热点",
    experience: "实践复盘、踩坑记录",
    dev: "接口设计与架构方案",
    engineering: "接口设计与架构方案",
  };

  return labels[board.slug] ?? board.description;
}
</script>

<template>
  <div class="board-directory-page">
    <header class="discover-hero">
      <h1>发现内容</h1>
      <p>按版块进入，按标签筛选。</p>

      <label class="discover-search" for="board-directory-search">
        <SearchOutlined aria-hidden="true" />
        <input
          id="board-directory-search"
          v-model="searchQuery"
          type="search"
          placeholder="搜索版块或标签"
          autocomplete="off"
        />
      </label>
    </header>

    <div v-if="boardsQuery.isError.value || tagsQuery.isError.value" class="directory-state directory-state--error" role="alert">
      部分入口暂时不可用，请稍后刷新。
    </div>

    <main class="discover-stack" aria-label="内容发现入口">
      <section class="discover-section" aria-labelledby="recommended-boards-title">
        <div class="section-head">
          <h2 id="recommended-boards-title">
            <StarFilled aria-hidden="true" />
            推荐版块
          </h2>
          <button
            v-if="hasExpandableRecommendedBoards"
            type="button"
            @click="showAllRecommendedBoards = !showAllRecommendedBoards"
          >
            {{ showAllRecommendedBoards ? "收起" : "查看更多" }}
            <UpOutlined v-if="showAllRecommendedBoards" aria-hidden="true" />
            <RightOutlined v-else aria-hidden="true" />
          </button>
        </div>

        <div v-if="boardsQuery.isLoading.value" class="recommended-grid" role="status" aria-label="正在加载推荐版块">
          <span v-for="item in 4" :key="item" class="recommended-skeleton"></span>
        </div>
        <p v-else-if="!recommendedBoards.length" class="directory-state">暂无匹配版块</p>
        <div v-else class="recommended-grid">
          <RouterLink
            v-for="board in recommendedBoards"
            :key="board.id"
            class="recommended-card"
            :class="boardToneClass(board.slug)"
            :to="{ name: 'board-detail', params: { slug: board.slug } }"
          >
            <span class="recommended-card__top">
              <span class="recommended-icon">
                <component :is="boardIcon(board)" aria-hidden="true" />
              </span>
              <span>
                <strong>{{ board.name }}</strong>
                <small>{{ boardPurpose(board) }}</small>
              </span>
            </span>
            <em>{{ compactNumber(board.topicCount) }} 个主题</em>
          </RouterLink>
        </div>
      </section>

      <section v-if="listedBoards.length || boardsQuery.isLoading.value" class="discover-section" aria-labelledby="all-boards-title">
        <div class="section-head">
          <h2 id="all-boards-title">
            <AppstoreOutlined aria-hidden="true" />
            全部版块
          </h2>
          <button v-if="hasHiddenBoards" type="button" @click="showAllBoards = true">
            查看全部
            <RightOutlined aria-hidden="true" />
          </button>
        </div>

        <div v-if="boardsQuery.isLoading.value" class="board-chip-grid" role="status" aria-label="正在加载版块">
          <span v-for="item in 6" :key="item" class="chip-skeleton"></span>
        </div>
        <div v-else class="board-chip-grid">
          <RouterLink
            v-for="board in listedBoards"
            :key="board.id"
            class="board-chip"
            :class="boardToneClass(board.slug)"
            :to="{ name: 'board-detail', params: { slug: board.slug } }"
          >
            <component :is="boardIcon(board)" aria-hidden="true" />
            <span>{{ board.name }}</span>
          </RouterLink>
        </div>
      </section>

      <section v-if="listedTags.length || tagsQuery.isLoading.value" class="discover-section" aria-labelledby="hot-tags-title">
        <div class="section-head">
          <h2 id="hot-tags-title">
            <TagsOutlined aria-hidden="true" />
            热门标签
          </h2>
          <button v-if="hasHiddenTags" type="button" @click="showAllTags = true">
            查看全部
            <RightOutlined aria-hidden="true" />
          </button>
        </div>

        <div v-if="tagsQuery.isLoading.value" class="tag-chip-grid" role="status" aria-label="正在加载标签">
          <span v-for="item in 8" :key="item" class="chip-skeleton"></span>
        </div>
        <div v-else class="tag-chip-grid">
          <RouterLink
            v-for="tag in listedTags"
            :key="tag.id"
            class="tag-chip"
            :style="tagAccentStyle(tag.name)"
            :to="{ name: 'search', query: { q: tag.name, tag: tag.name } }"
          >
            <component :is="tagIcon(tag.name)" aria-hidden="true" />
            <span># {{ tag.name }}</span>
            <em>{{ compactNumber(tag.topicCount) }}</em>
          </RouterLink>
          <RouterLink v-if="!hasSearch && showAllTags" class="tag-chip tag-chip--all" :to="{ name: 'search' }">
            <UnorderedListOutlined aria-hidden="true" />
            <span>所有标签</span>
          </RouterLink>
        </div>
      </section>

      <RouterLink v-if="!hasSearch" class="latest-topic-link" :to="{ name: 'home' }">
        <CompassOutlined aria-hidden="true" />
        <span>
          <strong>不知道去哪？</strong>
          <small>看看大家在聊什么</small>
        </span>
        <em>
          浏览最新主题
          <RightOutlined aria-hidden="true" />
        </em>
      </RouterLink>
    </main>

    <div v-if="!boardsQuery.isLoading.value && !tagsQuery.isLoading.value && !hasVisibleResults" class="directory-state">
      没有匹配的版块或标签。
    </div>
  </div>
</template>

<style scoped lang="scss" src="./BoardDirectoryPage.scss"></style>
