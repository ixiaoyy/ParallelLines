<script setup lang="ts">
import { computed, ref } from "vue";

import type { BoardSummary } from "@/entities/board/model";
import { sortBoardsWithFeedbackLast } from "@/entities/board/order";
import { useBoards } from "@/features/boards/queries";
import { useTopicFeed } from "@/features/topics/queries";
import { boardToneClass } from "@/shared/theme/boardPalette";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import UiBadge from "@/shared/ui/Badge.vue";
import UiCard from "@/shared/ui/Card.vue";

const searchQuery = ref("");
const boardsQuery = useBoards();
const topicsQuery = useTopicFeed("latest");

const boardItems = computed(() => {
  const boards = boardsQuery.data.value ?? [];
  return sortBoardsWithFeedbackLast(
    boards,
    (left, right) => right.topicCount + right.postCount - (left.topicCount + left.postCount),
  );
});

const topicItems = computed(() => topicsQuery.data.value ?? []);
const intentShortcuts = computed(() =>
  boardItems.value.slice(0, 4).map((board) => ({
    label: board.name,
    hint: board.description,
    to: { name: "board-detail", params: { slug: board.slug } },
  })),
);

const directorySignals = computed(() => [
  {
    label: "待首答",
    value: compactNumber(topicItems.value.filter((topic) => topic.status === "open" && topic.replyCount === 0).length),
    helper: "等待首个回复",
  },
  {
    label: "已解决",
    value: compactNumber(topicItems.value.filter((topic) => topic.solved).length),
    helper: "可直接复用的案例",
  },
  {
    label: "官方/精华",
    value: compactNumber(
      topicItems.value.filter((topic) => topic.officialReply || topic.featured || topic.pinned).length,
    ),
    helper: "高可信入口",
  },
]);

const featuredTopics = computed(() =>
  topicItems.value
    .filter((topic) => topic.solved || topic.officialReply || topic.featured || topic.pinned)
    .slice(0, 4),
);

const filteredBoards = computed(() => {
  const keyword = normalizeSearch(searchQuery.value);

  if (!keyword) {
    return boardItems.value;
  }

  return boardItems.value.filter((board) => {
    const previewText = getTopicsByBoardSlugLocal(board.slug)
      .map((topic) => `${topic.title} ${topic.excerpt} ${topic.tags.join(" ")}`)
      .join(" ");
    return normalizeSearch(`${board.name} ${board.description} ${board.slug} ${previewText}`).includes(keyword);
  });
});

function normalizeSearch(value: string) {
  return value.trim().toLocaleLowerCase();
}

function previewTopics(board: BoardSummary) {
  return getTopicsByBoardSlugLocal(board.slug)
    .filter((topic) => topic.solved || topic.officialReply || topic.replyCount === 0 || topic.featured || topic.pinned)
    .slice(0, 2);
}

// boardMark 用途：生成单字版块徽标，避免多字在方形标记中换行溢出；无副作用。
function boardMark(board: BoardSummary) {
  const labels: Record<string, string> = {
    announcements: "公",
    comics: "漫",
    community: "社",
    dev: "开",
    engineering: "工",
    experience: "验",
    feedback: "馈",
    frontier: "前",
    frontend: "前",
    health: "健",
    lounge: "聊",
    news: "新",
    plugins: "插",
    qna: "问",
    questions: "问",
    reading: "读",
    resources: "资",
    support: "问",
  };

  return (labels[board.slug] ?? board.name.trim().slice(0, 1)) || "版";
}

function boardIntent(board: BoardSummary) {
  if (board.parentBoardName) {
    return `子版块 · ${board.parentBoardName}`;
  }

  const labels: Record<string, string> = {
    announcements: "版本通知 / 维护窗口",
    comics: "每日漫画 / 连载推荐",
    support: "报错定位 / 可复现排查",
    dev: "接口设计 / 架构方案",
    plugins: "主题组件 / 编辑器体验",
    community: "规则共识 / 运营反馈",
  };

  return labels[board.slug] ?? "按主题进入";
}

function boardSignals(board: BoardSummary) {
  const boardTopics = getTopicsByBoardSlugLocal(board.slug);

  return [
    { label: "可查主题", value: compactNumber(board.topicCount) },
    { label: "已解决", value: compactNumber(boardTopics.filter((topic) => topic.solved).length) },
    { label: "未回复", value: compactNumber(boardTopics.filter((topic) => topic.replyCount === 0).length) },
  ];
}

function getTopicsByBoardSlugLocal(slug: string) {
  return topicItems.value.filter((topic) => topic.boardSlug === slug);
}
</script>

<template>
  <div class="board-directory-page">
    <section class="boards-hero" aria-labelledby="boards-title">
      <div class="boards-hero__copy">
        <UiBadge tone="blue">浏览入口</UiBadge>
        <h1 id="boards-title">先搜索问题，再选择版块。</h1>
        <p>
          输入错误码、接口名、日志关键词或问题现象；如果还不确定归属，再用下面的意图入口进入对应问题区。
        </p>

        <label class="board-search" for="board-directory-search">
          <span>搜索主题、标签或版块</span>
          <input
            id="board-directory-search"
            v-model="searchQuery"
            type="search"
            placeholder="例如：500 Error、请求超时、OIDC、Markdown"
            autocomplete="off"
          />
        </label>

        <div class="intent-shortcuts" aria-label="常见问题入口">
          <RouterLink v-for="shortcut in intentShortcuts" :key="shortcut.label" :to="shortcut.to">
            <strong>{{ shortcut.label }}</strong>
            <span>{{ shortcut.hint }}</span>
          </RouterLink>
        </div>
      </div>

      <div class="boards-hero__signals" aria-label="可操作线索">
        <div v-for="signal in directorySignals" :key="signal.label">
          <span>{{ signal.label }}</span>
          <strong>{{ signal.value }}</strong>
          <small>{{ signal.helper }}</small>
        </div>
      </div>
    </section>

    <div class="board-directory-layout">
      <main class="board-results" aria-label="版块列表">
        <UiCard v-if="boardsQuery.isError.value || topicsQuery.isError.value" class="directory-api-error" role="alert">
          部分内容暂时加载失败，请稍后刷新。
        </UiCard>

        <div class="board-results__heading">
          <div>
            <UiBadge tone="green">{{ searchQuery ? "搜索结果" : "推荐路径" }}</UiBadge>
            <h2>{{ searchQuery ? `匹配 “${searchQuery}” 的版块` : "按问题意图进入" }}</h2>
          </div>
          <span>{{ filteredBoards.length }} 个入口 · 优先看已解决与官方回复</span>
        </div>

        <section v-if="filteredBoards.length" class="board-grid">
          <article
            v-for="board in filteredBoards"
            :key="board.id"
            class="board-tile"
            :class="boardToneClass(board.slug)"
          >
            <RouterLink class="board-tile__main" :to="{ name: 'board-detail', params: { slug: board.slug } }">
              <span class="board-mark" :title="board.name">
                <span class="board-mark__text">{{ boardMark(board) }}</span>
              </span>
              <span class="board-copy">
                <span class="board-kicker">{{ boardIntent(board) }}</span>
                <strong>{{ board.name }}</strong>
                <em>{{ board.description }}</em>
              </span>
            </RouterLink>

            <dl class="board-signal-list">
              <div v-for="signal in boardSignals(board)" :key="signal.label">
                <dt>{{ signal.label }}</dt>
                <dd>{{ signal.value }}</dd>
              </div>
            </dl>

            <div class="board-topic-preview" aria-label="精选主题">
              <span class="board-topic-preview__label">推荐先看</span>
              <RouterLink
                v-for="topic in previewTopics(board)"
                :key="topic.id"
                :to="topicDetailRoute(topic)"
              >
                <span>{{ topic.title }}</span>
                <small>
                  {{ topic.solved ? "已解决" : topic.officialReply ? "官方回复" : `${compactNumber(topic.replyCount)} 回复` }} ·
                  {{ relativeTime(topic.lastPostedAt) }}
                </small>
              </RouterLink>
              <span v-if="previewTopics(board).length === 0" class="empty-preview">暂无精选主题，进入后查看全部主题</span>
            </div>

            <footer class="board-actions">
              <span>可先查看内容；登录后再关注通知。</span>
              <RouterLink class="open-board-link" :to="{ name: 'board-detail', params: { slug: board.slug } }">
                查看相关问题
              </RouterLink>
            </footer>
          </article>
        </section>

        <UiCard v-else class="no-board-results">
          <h2>没有匹配的版块</h2>
          <p>换一个错误码、接口名或中文症状试试，例如 “OIDC”、“导入超时”、“Markdown”。</p>
        </UiCard>
      </main>

      <aside class="board-directory-sidebar" aria-label="版块侧边栏">
        <UiCard class="sidebar-panel spotlight-panel">
          <div class="sidebar-panel__head">
            <span class="panel-kicker">精选入口</span>
            <h2>优先从这些主题开始</h2>
          </div>
          <ul>
            <li v-for="topic in featuredTopics" :key="topic.id">
              <RouterLink :to="topicDetailRoute(topic)">{{ topic.title }}</RouterLink>
              <small>{{ topic.boardName }} · {{ topic.solved ? "已解决" : topic.officialReply ? "官方回复" : "精华" }}</small>
            </li>
          </ul>
        </UiCard>

        <UiCard class="sidebar-panel guide-panel">
          <div class="sidebar-panel__head">
            <span class="panel-kicker">发帖前</span>
            <p class="guide-panel__lead">让问题更快得到回复</p>
          </div>
          <ol class="guide-panel__steps">
            <li>先搜错误码、接口名、日志关键字。</li>
            <li>排障类主题附环境、复现步骤和完整报错。</li>
            <li>如果已有相似主题，优先补充你的差异信息。</li>
          </ol>
        </UiCard>
      </aside>
    </div>
  </div>
</template>

<style scoped lang="scss" src="./BoardDirectoryPage.scss"></style>
