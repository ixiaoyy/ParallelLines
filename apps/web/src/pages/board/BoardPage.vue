<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useBoardDetail } from "@/features/boards/queries";
import { setBoardFollow } from "@/features/interactions/api";
import { useOptimisticToggle } from "@/features/interactions/useOptimisticToggle";
import TopicList from "@/features/topics/components/TopicList.vue";
import { useBoardTopics } from "@/features/topics/queries";
import { hasAccessToken } from "@/shared/api/client";
import { compactNumber } from "@/shared/lib/format";
import { readRouteParam } from "@/shared/router/params";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";
import UiEmptyState from "@/shared/ui/EmptyState.vue";

type BoardSort = "latest" | "hot" | "top";
type TopicStatusFilter = "all" | "solved" | "unanswered" | "official";

const sortTabs: Array<{ key: BoardSort; label: string; helper: string }> = [
  { key: "latest", label: "最新", helper: "按最后回复时间" },
  { key: "hot", label: "热门", helper: "按热度与讨论" },
  { key: "top", label: "高信号", helper: "按赞同与回复" },
];

const statusFilters: Array<{ key: TopicStatusFilter; label: string }> = [
  { key: "all", label: "全部" },
  { key: "solved", label: "已解决" },
  { key: "unanswered", label: "未回复" },
  { key: "official", label: "官方回复" },
];

const route = useRoute();
const router = useRouter();

const slug = computed(() => readRouteParam(route.params.slug));
const boardQuery = useBoardDetail(slug);
const board = computed(() => boardQuery.data.value);
const {
  active: followingBoard,
  count: followerCount,
  pending: followPending,
  toggle: toggleBoardFollow,
} = useOptimisticToggle({
  active: () => board.value?.isFollowing ?? false,
  count: () => board.value?.followerCount ?? 0,
  enabled: hasAccessToken,
  commit: (active) => setBoardFollow(slug.value, active),
  readActive: (response) => response.following,
  readCount: (response) => response.follower_count,
});

const searchQuery = computed<string>({
  get() {
    return readRouteParam(route.query.q as string | string[] | undefined);
  },
  set(value) {
    updateQuery({ q: value.trim() || undefined });
  },
});

const activeSort = computed<BoardSort>({
  get() {
    const querySort = readRouteParam(route.query.sort as string | string[] | undefined);
    return sortTabs.some((tab) => tab.key === querySort) ? (querySort as BoardSort) : "latest";
  },
  set(value) {
    updateQuery({ sort: value === "latest" ? undefined : value });
  },
});

const activeStatus = computed<TopicStatusFilter>({
  get() {
    const queryStatus = readRouteParam(route.query.status as string | string[] | undefined);
    return statusFilters.some((filter) => filter.key === queryStatus) ? (queryStatus as TopicStatusFilter) : "all";
  },
  set(value) {
    updateQuery({ status: value === "all" ? undefined : value });
  },
});

const activeTab = computed(() => sortTabs.find((tab) => tab.key === activeSort.value) ?? sortTabs[0]);
const topicsQuery = useBoardTopics(slug, activeSort);

const allBoardTopics = computed(() => topicsQuery.data.value ?? board.value?.latestTopics ?? []);

const sortedBoardTopics = computed(() => {
  const list = [...allBoardTopics.value];

  if (activeSort.value === "hot") {
    return list.sort((left, right) => right.hotScore - left.hotScore);
  }

  if (activeSort.value === "top") {
    return list.sort((left, right) => right.likeCount + right.replyCount - (left.likeCount + left.replyCount));
  }

  return list.sort((left, right) => Date.parse(right.lastPostedAt) - Date.parse(left.lastPostedAt));
});

const boardTopics = computed(() => {
  const keyword = searchQuery.value.trim().toLocaleLowerCase();

  return sortedBoardTopics.value.filter((topic) => {
    const matchesKeyword = keyword
      ? `${topic.title} ${topic.excerpt} ${topic.tags.join(" ")}`.toLocaleLowerCase().includes(keyword)
      : true;
    const matchesStatus =
      activeStatus.value === "all" ||
      (activeStatus.value === "solved" && topic.solved) ||
      (activeStatus.value === "unanswered" && topic.replyCount === 0) ||
      (activeStatus.value === "official" && topic.officialReply);

    return matchesKeyword && matchesStatus;
  });
});

const solutionStats = computed(() => {
  const topicsInBoard = allBoardTopics.value;

  return [
    { label: "已解决", value: compactNumber(topicsInBoard.filter((topic) => topic.solved).length), helper: "可直接比对" },
    { label: "未回复", value: compactNumber(topicsInBoard.filter((topic) => topic.replyCount === 0).length), helper: "等待首答" },
    { label: "官方回复", value: compactNumber(topicsInBoard.filter((topic) => topic.officialReply).length), helper: "团队已介入" },
    { label: "关注者", value: compactNumber(followerCount.value), helper: followingBoard.value ? "正在接收通知" : "可一键关注" },
  ];
});

const searchPlaceholder = computed(() => {
  if (slug.value === "support") {
    return "搜索错误码、日志、OIDC、升级失败……";
  }

  return "搜索主题、标签、接口名或问题现象";
});

function boardMark(name: string) {
  return name.includes("与") ? name.split("与")[0] : name;
}

function updateQuery(patch: Record<string, string | undefined>) {
  const query = { ...route.query };

  Object.entries(patch).forEach(([key, value]) => {
    if (value) {
      query[key] = value;
      return;
    }

    delete query[key];
  });

  void router.replace({ name: "board-detail", params: { slug: slug.value }, query });
}
</script>

<template>
  <div class="board-page">
    <UiCard v-if="boardQuery.isLoading.value" class="board-state" role="status">
      正在加载版块…
    </UiCard>

    <UiEmptyState
      v-else-if="boardQuery.isError.value"
      title="无法加载这个版块"
      description="这个版块暂时无法访问，请稍后重试或返回版块目录。"
    >
      <RouterLink class="empty-link" to="/boards">返回版块目录</RouterLink>
    </UiEmptyState>

    <template v-else-if="board">
      <section class="board-hero" :style="{ '--board-color': board.color }" aria-labelledby="board-title">
        <div class="board-hero__header">
          <span class="board-hero__mark" aria-hidden="true">{{ boardMark(board.name) }}</span>
          <div class="board-hero__copy">
            <div class="board-breadcrumb">
              <RouterLink to="/boards">全部版块</RouterLink>
              <span>/</span>
              <span>{{ board.name }}</span>
            </div>
            <h1 id="board-title">{{ board.name }}</h1>
            <p>{{ board.description }}</p>
          </div>
        </div>

        <label class="board-local-search" for="board-local-search">
          <span>在 {{ board.name }} 中搜索</span>
          <input
            id="board-local-search"
            v-model="searchQuery"
            type="search"
            :placeholder="searchPlaceholder"
            autocomplete="off"
          />
        </label>

        <div class="board-follow-strip">
          <span>{{ followingBoard ? "新主题会进入通知中心。" : "关注后，新主题会进入通知中心。" }}</span>
          <UiButton
            :tone="followingBoard ? 'success' : 'primary'"
            :aria-pressed="followingBoard"
            :disabled="followPending"
            @click="toggleBoardFollow"
          >
            {{ followingBoard ? "已关注版块" : "关注版块" }}
          </UiButton>
        </div>

        <dl class="board-hero__signals" aria-label="解答信号">
          <div v-for="signal in solutionStats" :key="signal.label">
            <dt>{{ signal.label }}</dt>
            <dd>{{ signal.value }}</dd>
            <span>{{ signal.helper }}</span>
          </div>
        </dl>
      </section>

      <div class="board-layout">
        <main class="board-main" aria-label="版块主题列表">
          <section class="board-toolbar" aria-label="主题筛选">
            <div class="board-tabs" aria-label="排序方式">
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
            </div>

            <div class="status-filters" aria-label="解答状态">
              <button
                v-for="filter in statusFilters"
                :key="filter.key"
                type="button"
                :class="{ active: activeStatus === filter.key }"
                @click="activeStatus = filter.key"
              >
                {{ filter.label }}
              </button>
            </div>
          </section>

          <div class="board-feed-heading">
            <h2>{{ board.name }}主题</h2>
            <span>
              {{ activeTab.label }} · {{ activeTab.helper }} · {{ boardTopics.length }} / {{ allBoardTopics.length }} 条
              {{ searchQuery ? `· 搜索 “${searchQuery}”` : "" }}
            </span>
          </div>

          <UiCard v-if="topicsQuery.isError.value" class="board-state board-state--error" role="alert">
            主题列表暂时加载失败，请稍后刷新。
          </UiCard>
          <TopicList :topics="boardTopics" />
        </main>

        <aside class="board-sidebar" aria-label="版块信息">
          <UiCard class="sidebar-panel rules-panel">
            <span class="panel-kicker">提问前自检</span>
            <h2>先让答案更快出现</h2>
            <ol>
              <li>先搜错误码、接口名、日志片段。</li>
              <li>优先阅读“已解决”和“官方回复”。</li>
              <li>仍未命中时，发布新问题并附环境、复现步骤、期望结果。</li>
            </ol>
            <RouterLink class="ask-link" :to="{ name: 'new-topic', query: { board: slug } }">发布新问题</RouterLink>
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
