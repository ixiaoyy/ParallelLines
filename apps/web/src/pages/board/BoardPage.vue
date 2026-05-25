<script setup lang="ts">
import {
  SearchOutlined,
  CheckCircleOutlined,
  CompassOutlined,
  FileTextOutlined,
  FireOutlined,
  HeartOutlined,
  HistoryOutlined,
  QuestionCircleOutlined,
  RightOutlined,
  StarFilled,
  StarOutlined,
  TeamOutlined,
  BulbOutlined,
} from "@ant-design/icons-vue";
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { isAdmin } from "@/features/auth/permissions";
import { useCurrentUser } from "@/features/auth/queries";
import BoardSettingsPanel from "@/features/boards/components/BoardSettingsPanel.vue";
import { useBoardDetail } from "@/features/boards/queries";
import { setBoardFollow } from "@/features/interactions/api";
import { useOptimisticToggle } from "@/features/interactions/useOptimisticToggle";
import type { NotificationLevel } from "@/features/notifications/model";
import TopicList from "@/features/topics/components/TopicList.vue";
import { useBoardTopics } from "@/features/topics/queries";
import { hasAccessToken } from "@/shared/api/client";
import { compactNumber } from "@/shared/lib/format";
import { readRouteParam } from "@/shared/router/params";
import { useSeoMeta } from "@/shared/seo/meta";
import { boardToneClass } from "@/shared/theme/boardPalette";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";
import UiEmptyState from "@/shared/ui/EmptyState.vue";

type BoardSort = "latest" | "hot" | "top";
type TopicStatusFilter = "all" | "solved" | "unanswered" | "official";

const notificationLevelOptions: Array<{ value: NotificationLevel; label: string }> = [
  { value: "watching", label: "关注 · 新主题通知" },
  { value: "tracking", label: "跟踪 · 精简通知" },
  { value: "normal", label: "普通 · 不主动提醒" },
  { value: "muted", label: "静音 · 不接收通知" },
];

const boardIcons: Record<string, string> = {
  engineering: `<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <path d="M26 60V18M38 60V18" />
    <path d="M26 50h12M26 40h12M26 30h12M26 20h12" />
    <path d="M26 50l12-10M26 40l12-10M26 30l12-10M26 20l12-8" />
    <path d="M20 60h24" />
    <path d="M8 18h48" />
    <path d="M12 18l14-10h12" />
    <rect x="46" y="21" width="6" height="8" rx="1" fill="currentColor" />
    <rect x="18" y="18" width="4" height="3" fill="currentColor" />
    <path d="M20 21v10" />
    <circle cx="20" cy="33" r="2" />
  </svg>`,
  announcements: `<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M10 20h10l16-12v40L20 36H10a2 2 0 0 1-2-2V22a2 2 0 0 1 2-2z" />
    <path d="M36 28h4v4h-4z" />
    <path d="M44 20c3 3.5 3 10.5 0 14M49 14c6 6.5 6 19.5 0 26" />
    <path d="M18 36v12a4 4 0 0 0 8 0V36" />
  </svg>`,
  support: `<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="32" cy="32" r="22" />
    <circle cx="32" cy="32" r="10" />
    <path d="M16 16l11 11M48 16L37 27M16 48l11-11M48 48L37 37" />
    <path d="M22 10a22 22 0 0 1 20 0M54 22a22 22 0 0 1 0 20M42 54a22 22 0 0 1-20 0M10 42a22 22 0 0 1 0-20" opacity="0.3" />
  </svg>`,
  frontend: `<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <rect x="8" y="10" width="48" height="34" rx="3" />
    <path d="M20 54h24M32 44v10" />
    <path d="M20 22l-6 5 6 5M44 22l6 5-6 5M35 19l-6 16" />
  </svg>`,
  plugins: `<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M44 28V16a4 4 0 0 0-4-4h-4a4 4 0 0 1-4-4 4 4 0 0 1-4 4h-4a4 4 0 0 0-4 4v12a4 4 0 0 1-4 4H10v8h10a4 4 0 0 1 4 4v12h12v-6a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v6h8V28h-6a4 4 0 0 1-4-4z" />
  </svg>`,
  community: `<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M14 38v8l8-4h18a4 4 0 0 0 4-4V22a4 4 0 0 0-4-4H14a4 4 0 0 0-4 4v12a4 4 0 0 0 4 4z" />
    <path d="M48 18h2a4 4 0 0 1 4 4v12a4 4 0 0 1-4 4h-6l-6 4v-4" />
  </svg>`
};

function getBoardIcon(slug: string): string | undefined {
  return boardIcons[slug];
}

function getSortIcon(key: string) {
  if (key === "latest") return HistoryOutlined;
  if (key === "hot") return FireOutlined;
  return CheckCircleOutlined;
}

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
const currentUserQuery = useCurrentUser();
const boardQuery = useBoardDetail(slug);
const board = computed(() => boardQuery.data.value);
useSeoMeta(
  computed(() =>
    board.value
      ? {
          title: `${board.value.name} · 平行线`,
          description: board.value.description,
          canonicalPath: `/b/${board.value.slug}`,
        }
      : null,
  ),
);
const canManageBoard = computed(
  () =>
    Boolean(board.value?.ownerId && board.value.ownerId === currentUserQuery.data.value?.id) ||
    isAdmin(currentUserQuery.data.value),
);
const boardNotificationLevel = ref<NotificationLevel>("watching");
const boardNotificationPending = ref(false);
const {
  active: followingBoard,
  count: followerCount,
  pending: followPending,
  toggle: toggleBoardFollow,
} = useOptimisticToggle({
  active: () => board.value?.isFollowing ?? false,
  count: () => board.value?.followerCount ?? 0,
  enabled: hasAccessToken,
  commit: (active) => setBoardFollow(slug.value, active, boardNotificationLevel.value),
  readActive: (response) => response.following,
  readCount: (response) => response.follower_count,
});

watch(
  board,
  (current) => {
    if (!current || boardNotificationPending.value) {
      return;
    }

    boardNotificationLevel.value = toNotificationLevel(current.notificationLevel) ?? "watching";
  },
  { immediate: true },
);

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
    return sortTabs.some((tab) => tab.key === querySort)
      ? (querySort as BoardSort)
      : (board.value?.defaultSort ?? "latest");
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
const boardNotificationCopy = computed(() => {
  if (!followingBoard.value) {
    return "关注此版块，不错过任何新主题";
  }

  if (boardNotificationLevel.value === "muted") {
    return "已静音此版块，新主题不会打扰你";
  }

  if (boardNotificationLevel.value === "tracking") {
    return "已跟踪此版块，只接收精简通知";
  }

  if (boardNotificationLevel.value === "normal") {
    return "已加入版块，但不主动推送新主题";
  }

  return "已开启版块通知，新主题发布时将通知您";
});

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
    { label: "未回复", value: compactNumber(topicsInBoard.filter((topic) => topic.replyCount === 0).length), helper: "等待解答" },
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
  const base = name.includes("与") ? name.split("与")[0] : name;
  return base.slice(0, 2);
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

function toNotificationLevel(value: string | null): NotificationLevel | null {
  if (
    value === "watching" ||
    value === "tracking" ||
    value === "normal" ||
    value === "muted"
  ) {
    return value;
  }

  return null;
}

async function updateBoardNotificationLevel(event: Event) {
  const target = event.target as HTMLSelectElement;
  const nextLevel = target.value as NotificationLevel;
  const previousLevel = boardNotificationLevel.value;
  boardNotificationLevel.value = nextLevel;

  if (!hasAccessToken()) {
    void router.push({ name: "auth", query: { redirect: route.fullPath } });
    return;
  }

  boardNotificationPending.value = true;
  try {
    const response = await setBoardFollow(slug.value, true, nextLevel);
    followingBoard.value = response.following;
    followerCount.value = response.follower_count;
    boardNotificationLevel.value = response.notification_level ?? nextLevel;
  } catch {
    boardNotificationLevel.value = previousLevel;
  } finally {
    boardNotificationPending.value = false;
  }
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
      <section class="board-hero" :class="boardToneClass(board.slug)" aria-labelledby="board-title">
        <div v-if="slug === 'engineering'" class="board-hero__bg-illustration" v-html="boardIcons.engineering" aria-hidden="true"></div>
        <div class="board-hero__header">
          <span
            class="board-hero__mark"
            :class="`board-hero__mark--${board.slug}`"
            aria-hidden="true"
            v-html="getBoardIcon(board.slug) || boardMark(board.name)"
          ></span>
          <div class="board-hero__copy">
            <div class="board-breadcrumb">
              <RouterLink to="/boards">全部版块</RouterLink>
              <span>/</span>
              <span>{{ board.name }}</span>
            </div>
            <div class="board-title-row">
              <h1 id="board-title">{{ board.name }}</h1>
              <div class="board-follow-controls">
                <UiButton
                  class="board-follow-btn"
                  :tone="followingBoard ? 'success' : 'subtle'"
                  :aria-pressed="followingBoard"
                  :disabled="followPending || boardNotificationPending"
                  @click="toggleBoardFollow"
                >
                  <template #icon>
                    <StarFilled v-if="followingBoard" />
                    <StarOutlined v-else />
                  </template>
                  {{ followingBoard ? "已关注版块" : "关注版块" }}
                </UiButton>
                <label class="board-notification-select">
                  <span>版块通知</span>
                  <select
                    :value="boardNotificationLevel"
                    :disabled="followPending || boardNotificationPending"
                    aria-label="设置版块通知级别"
                    @change="updateBoardNotificationLevel"
                  >
                    <option
                      v-for="option in notificationLevelOptions"
                      :key="option.value"
                      :value="option.value"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                </label>
              </div>
            </div>
            <p class="board-desc">{{ board.description }}</p>
            <p class="board-notice">
              <span class="notice-dot"></span>
              {{ boardNotificationCopy }}
            </p>
          </div>
        </div>

        <div class="board-hero__signals" aria-label="解答信号">
          <div class="signal-card signal-card--solved">
            <div class="signal-icon-wrapper">
              <CheckCircleOutlined />
            </div>
            <div class="signal-info">
              <span class="signal-label">已解决</span>
              <strong class="signal-value">{{ solutionStats[0].value }}</strong>
              <span class="signal-helper">可直接比对</span>
            </div>
          </div>
          <div class="signal-card signal-card--unanswered">
            <div class="signal-icon-wrapper">
              <QuestionCircleOutlined />
            </div>
            <div class="signal-info">
              <span class="signal-label">未回复</span>
              <strong class="signal-value">{{ solutionStats[1].value }}</strong>
              <span class="signal-helper">等待解答</span>
            </div>
          </div>
          <div class="signal-card signal-card--official">
            <div class="signal-icon-wrapper">
              <TeamOutlined />
            </div>
            <div class="signal-info">
              <span class="signal-label">官方回复</span>
              <strong class="signal-value">{{ solutionStats[2].value }}</strong>
              <span class="signal-helper">团队已介入</span>
            </div>
          </div>
          <div class="signal-card signal-card--followers">
            <div class="signal-icon-wrapper">
              <HeartOutlined />
            </div>
            <div class="signal-info">
              <span class="signal-label">关注者</span>
              <strong class="signal-value">{{ solutionStats[3].value }}</strong>
              <span class="signal-helper">{{ followingBoard ? '正在接收通知' : '可一键关注' }}</span>
            </div>
          </div>
        </div>
      </section>

      <div class="board-layout" :class="boardToneClass(board.slug)">
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
                <div class="tab-content">
                  <component :is="getSortIcon(tab.key)" class="tab-icon" />
                  <div class="tab-text">
                    <strong>{{ tab.label }}</strong>
                    <span>{{ tab.helper }}</span>
                  </div>
                </div>
              </button>
            </div>

            <div class="board-toolbar__actions">
              <div class="board-search-wrapper">
                <SearchOutlined class="search-icon" />
                <input
                  v-model="searchQuery"
                  type="search"
                  :placeholder="searchPlaceholder"
                  autocomplete="off"
                  class="board-search-input"
                />
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
            <p v-if="board.requiredTags.length" class="board-policy-copy">
              必填标签：{{ board.requiredTags.map((tag) => `#${tag}`).join(" ") }}
            </p>
            <ol>
              <li>先搜错误码、接口名、日志片段。</li>
              <li>优先阅读“已解决”和“官方回复”。</li>
              <li>仍未命中时，发布新问题并附环境、复现步骤、期望结果。</li>
            </ol>
            <RouterLink class="ask-link" :to="{ name: 'new-topic', query: { board: slug } }">发布新问题</RouterLink>
          </UiCard>

          <UiCard v-if="board.childBoards.length" class="sidebar-panel child-board-panel">
            <span class="panel-kicker">子版块</span>
            <h2>继续细分讨论范围</h2>
            <RouterLink
              v-for="child in board.childBoards"
              :key="child.id"
              :to="{ name: 'board-detail', params: { slug: child.slug } }"
            >
              <strong>{{ child.name }}</strong>
              <small>{{ child.topicCount }} 主题 · {{ child.description }}</small>
            </RouterLink>
          </UiCard>

          <BoardSettingsPanel v-if="canManageBoard" :board="board" />

          <UiCard class="sidebar-panel quick-links-panel">
            <h2>快捷入口</h2>
            <div class="quick-links">
              <a href="#" class="quick-link-item" @click.prevent>
                <div class="quick-link-icon-wrapper">
                  <FileTextOutlined class="quick-link-icon" />
                </div>
                <div class="quick-link-text">
                  <h3>接口文档</h3>
                  <p>查看接口规范与示例</p>
                </div>
                <RightOutlined class="quick-link-arrow" />
              </a>
              <a href="#" class="quick-link-item" @click.prevent>
                <div class="quick-link-icon-wrapper">
                  <BulbOutlined class="quick-link-icon" />
                </div>
                <div class="quick-link-text">
                  <h3>常见问题</h3>
                  <p>汇总高频问题与方案</p>
                </div>
                <RightOutlined class="quick-link-arrow" />
              </a>
              <a href="#" class="quick-link-item" @click.prevent>
                <div class="quick-link-icon-wrapper">
                  <CompassOutlined class="quick-link-icon" />
                </div>
                <div class="quick-link-text">
                  <h3>社区指南</h3>
                  <p>了解提问规范与流程</p>
                </div>
                <RightOutlined class="quick-link-arrow" />
              </a>
            </div>
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
