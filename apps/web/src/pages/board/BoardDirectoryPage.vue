<script setup lang="ts">
import { computed, ref } from "vue";

import type { BoardSummary } from "@/entities/board/model";
import { boards, getTopicsByBoardSlug, tagCloud, topics } from "@/shared/api/mockForum";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const boardItems = ref<BoardSummary[]>(boards.map((board) => ({ ...board })));

const totals = computed(() => ({
  boards: boardItems.value.length,
  topics: boardItems.value.reduce((sum, board) => sum + board.topicCount, 0),
  followers: boardItems.value.reduce((sum, board) => sum + board.followerCount, 0),
}));

const activeBoards = computed(() =>
  [...boardItems.value].sort((left, right) => right.topicCount + right.postCount - (left.topicCount + left.postCount)),
);

const featuredTopics = computed(() => topics.filter((topic) => topic.featured || topic.pinned).slice(0, 4));

function previewTopics(board: BoardSummary) {
  return getTopicsByBoardSlug(board.slug).slice(0, 2);
}

function toggleFollow(slug: string) {
  boardItems.value = boardItems.value.map((board) =>
    board.slug === slug ? { ...board, isFollowing: !board.isFollowing } : board,
  );
}
</script>

<template>
  <div class="board-directory-page">
    <section class="boards-hero" aria-labelledby="boards-title">
      <div class="boards-hero__copy">
        <UiBadge tone="blue">版块导航</UiBadge>
        <h1 id="boards-title">选择一条平行线，进入对应的问题现场。</h1>
        <p>
          按主题语义组织讨论：公告沉淀决策，支持区定位问题，开发区讨论 API 与架构，插件区打磨体验，社区区处理规则共识。
        </p>
      </div>

      <div class="boards-hero__stats" aria-label="版块统计">
        <div>
          <span>开放版块</span>
          <strong>{{ totals.boards }}</strong>
        </div>
        <div>
          <span>累计主题</span>
          <strong>{{ compactNumber(totals.topics) }}</strong>
        </div>
        <div>
          <span>关注人数</span>
          <strong>{{ compactNumber(totals.followers) }}</strong>
        </div>
      </div>
    </section>

    <div class="board-directory-layout">
      <main class="board-grid" aria-label="版块列表">
        <article
          v-for="board in activeBoards"
          :key="board.id"
          class="board-tile"
          :style="{ '--board-color': board.color }"
        >
          <RouterLink class="board-tile__main" :to="{ name: 'board-detail', params: { slug: board.slug } }">
            <span class="board-mark" aria-hidden="true">{{ board.name.slice(0, 1) }}</span>
            <span class="board-copy">
              <span class="board-kicker">{{ board.isFollowing ? "正在追踪" : "开放加入" }}</span>
              <strong>{{ board.name }}</strong>
              <em>{{ board.description }}</em>
            </span>
          </RouterLink>

          <dl class="board-stats">
            <div>
              <dt>主题</dt>
              <dd>{{ compactNumber(board.topicCount) }}</dd>
            </div>
            <div>
              <dt>帖子</dt>
              <dd>{{ compactNumber(board.postCount) }}</dd>
            </div>
            <div>
              <dt>关注</dt>
              <dd>{{ compactNumber(board.followerCount) }}</dd>
            </div>
          </dl>

          <div class="board-topic-preview" aria-label="近期主题">
            <RouterLink
              v-for="topic in previewTopics(board)"
              :key="topic.id"
              :to="`/t/${topic.slug}/${topic.id}`"
            >
              <span>{{ topic.title }}</span>
              <small>{{ relativeTime(topic.lastPostedAt) }}</small>
            </RouterLink>
            <span v-if="previewTopics(board).length === 0" class="empty-preview">暂无前端示例主题</span>
          </div>

          <footer class="board-actions">
            <UiButton :tone="board.isFollowing ? 'subtle' : 'primary'" @click="toggleFollow(board.slug)">
              {{ board.isFollowing ? "调整通知" : "关注版块" }}
            </UiButton>
            <RouterLink class="open-board-link" :to="{ name: 'board-detail', params: { slug: board.slug } }">
              进入版块
            </RouterLink>
          </footer>
        </article>
      </main>

      <aside class="board-directory-sidebar" aria-label="版块侧边栏">
        <UiCard class="sidebar-panel spotlight-panel">
          <span class="panel-kicker">精选脉络</span>
          <h2>先从这些高信号主题进入</h2>
          <ul>
            <li v-for="topic in featuredTopics" :key="topic.id">
              <RouterLink :to="`/t/${topic.slug}/${topic.id}`">{{ topic.title }}</RouterLink>
              <small>{{ topic.boardName }} · {{ compactNumber(topic.replyCount) }} 回复</small>
            </li>
          </ul>
        </UiCard>

        <UiCard class="sidebar-panel">
          <span class="panel-kicker">热门标签</span>
          <h2>跨版块线索</h2>
          <div class="tag-cloud">
            <a v-for="tag in tagCloud" :key="tag" href="#tags">#{{ tag }}</a>
          </div>
        </UiCard>

        <UiCard class="sidebar-panel guide-panel">
          <span class="panel-kicker">发帖前</span>
          <h2>让问题更快被接住</h2>
          <ol>
            <li>标题写出症状、环境和期望结果。</li>
            <li>排障类主题附日志和最小复现步骤。</li>
            <li>提案类主题说明收益、成本和备选方案。</li>
          </ol>
        </UiCard>
      </aside>
    </div>
  </div>
</template>

<style scoped lang="scss" src="./BoardDirectoryPage.scss"></style>
