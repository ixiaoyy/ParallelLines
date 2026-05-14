<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import TopicList from "@/features/topics/components/TopicList.vue";
import {
  boards,
  getBoardBySlug,
  getTopicsByBoardSlug,
  readRouteParam,
  tagCloud,
} from "@/shared/api/mockForum";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";
import UiEmptyState from "@/shared/ui/EmptyState.vue";

type BoardSort = "latest" | "hot" | "top";

const sortTabs: Array<{ key: BoardSort; label: string; helper: string }> = [
  { key: "latest", label: "最新", helper: "按最后回复时间排序" },
  { key: "hot", label: "热门", helper: "按热度分排序" },
  { key: "top", label: "优质", helper: "按赞同和回复排序" },
];

const route = useRoute();
const router = useRouter();

const slug = computed(() => readRouteParam(route.params.slug));
const board = computed(() => getBoardBySlug(slug.value));

const activeSort = computed<BoardSort>({
  get() {
    const querySort = readRouteParam(route.query.sort as string | string[] | undefined);
    return sortTabs.some((tab) => tab.key === querySort) ? (querySort as BoardSort) : "latest";
  },
  set(value) {
    void router.replace({ name: "board-detail", params: { slug: slug.value }, query: { ...route.query, sort: value } });
  },
});

const activeTab = computed(() => sortTabs.find((tab) => tab.key === activeSort.value) ?? sortTabs[0]);

const boardTopics = computed(() => {
  if (!board.value) {
    return [];
  }

  const list = [...getTopicsByBoardSlug(board.value.slug)];

  if (activeSort.value === "hot") {
    return list.sort((left, right) => right.hotScore - left.hotScore);
  }

  if (activeSort.value === "top") {
    return list.sort((left, right) => right.likeCount + right.replyCount - (left.likeCount + left.replyCount));
  }

  return list.sort((left, right) => Date.parse(right.lastPostedAt) - Date.parse(left.lastPostedAt));
});

const neighboringBoards = computed(() => boards.filter((item) => item.slug !== slug.value).slice(0, 3));
const pinnedTopic = computed(() => boardTopics.value.find((topic) => topic.pinned || topic.featured) ?? boardTopics.value[0]);
</script>

<template>
  <div class="board-page">
    <template v-if="board">
      <section class="board-hero" :style="{ '--board-color': board.color }" aria-labelledby="board-title">
        <div class="board-hero__mark" aria-hidden="true">{{ board.name.slice(0, 1) }}</div>
        <div class="board-hero__copy">
          <div class="board-breadcrumb">
            <RouterLink to="/boards">全部版块</RouterLink>
            <span>/</span>
            <span>{{ board.name }}</span>
          </div>
          <h1 id="board-title">{{ board.name }}</h1>
          <p>{{ board.description }}</p>
          <div class="board-hero__actions">
            <UiButton tone="primary">发起主题</UiButton>
            <UiButton :tone="board.isFollowing ? 'subtle' : 'success'">
              {{ board.isFollowing ? "正在追踪" : "关注版块" }}
            </UiButton>
          </div>
        </div>
        <dl class="board-hero__stats">
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
      </section>

      <div class="board-layout">
        <main class="board-main" aria-label="版块主题列表">
          <UiCard v-if="pinnedTopic" class="board-highlight">
            <span class="panel-kicker">版块焦点</span>
            <RouterLink :to="`/t/${pinnedTopic.slug}/${pinnedTopic.id}`">{{ pinnedTopic.title }}</RouterLink>
            <p>{{ pinnedTopic.excerpt }}</p>
            <footer>
              <span>{{ compactNumber(pinnedTopic.replyCount) }} 回复</span>
              <span>{{ relativeTime(pinnedTopic.lastPostedAt) }}</span>
            </footer>
          </UiCard>

          <section class="board-tabs" aria-label="主题筛选">
            <button
              v-for="tab in sortTabs"
              :key="tab.key"
              type="button"
              :class="{ active: activeSort === tab.key }"
              @click="activeSort = tab.key"
            >
              <strong>{{ tab.label }}</strong>
              <span>{{ tab.helper }}</span>
            </button>
          </section>

          <div class="board-feed-heading">
            <div>
              <UiBadge tone="blue">{{ activeTab.label }}</UiBadge>
              <h2>{{ board.name }}主题</h2>
            </div>
            <span>{{ activeTab.helper }} · {{ boardTopics.length }} 条示例</span>
          </div>

          <TopicList :topics="boardTopics" />
        </main>

        <aside class="board-sidebar" aria-label="版块信息">
          <UiCard class="sidebar-panel rules-panel">
            <span class="panel-kicker">版块说明</span>
            <h2>发帖规则</h2>
            <ol>
              <li>排障主题需要包含环境、日志和复现路径。</li>
              <li>提案主题请说明影响范围和备选方案。</li>
              <li>重复主题会被合并，原链接会保留跳转。</li>
            </ol>
          </UiCard>

          <UiCard class="sidebar-panel">
            <span class="panel-kicker">值班版主</span>
            <h2>今天在线</h2>
            <div class="moderator-list">
              <span>林</span>
              <span>墨</span>
              <span>凯</span>
              <strong>响应中 · 12 分钟内</strong>
            </div>
          </UiCard>

          <UiCard class="sidebar-panel">
            <span class="panel-kicker">相关标签</span>
            <h2>常见线索</h2>
            <div class="tag-cloud">
              <a v-for="tag in tagCloud.slice(0, 6)" :key="tag" href="#tags">#{{ tag }}</a>
            </div>
          </UiCard>

          <UiCard class="sidebar-panel">
            <span class="panel-kicker">相邻版块</span>
            <h2>继续探索</h2>
            <RouterLink
              v-for="neighbor in neighboringBoards"
              :key="neighbor.id"
              class="neighbor-link"
              :to="{ name: 'board-detail', params: { slug: neighbor.slug } }"
              :style="{ '--neighbor-color': neighbor.color }"
            >
              <span aria-hidden="true"></span>
              <strong>{{ neighbor.name }}</strong>
              <small>{{ compactNumber(neighbor.topicCount) }} 主题</small>
            </RouterLink>
          </UiCard>
        </aside>
      </div>
    </template>

    <UiEmptyState v-else title="没有找到这个版块" description="可能是链接已变更，回到版块目录重新选择。">
      <RouterLink class="empty-link" to="/boards">返回版块目录</RouterLink>
    </UiEmptyState>
  </div>
</template>

<style scoped lang="scss" src="./BoardPage.scss"></style>
