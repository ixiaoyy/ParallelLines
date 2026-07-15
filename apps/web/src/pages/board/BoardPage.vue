<script setup lang="ts">
import {
  SearchOutlined,
  CheckCircleOutlined,
  FireOutlined,
  HistoryOutlined,
} from "@ant-design/icons-vue";
import { computed, defineAsyncComponent } from "vue";
import { useRoute, useRouter } from "vue-router";

import { publicSettingString } from "@/features/admin/model";
import { usePublicSiteSettings } from "@/features/admin/queries";
import { isAdmin } from "@/features/auth/permissions";
import { useCurrentUser } from "@/features/auth/queries";
import { useBoardDetail } from "@/features/boards/queries";
import TopicList from "@/features/topics/components/TopicList.vue";
import { useBoardTopics } from "@/features/topics/queries";
import { useAdminTopicDelete } from "@/features/topics/useAdminTopicDelete";
import { readRouteParam } from "@/shared/router/params";
import { useSeoMeta } from "@/shared/seo/meta";
import { boardToneClass } from "@/shared/theme/boardPalette";
import UiCard from "@/shared/ui/Card.vue";
import UiEmptyState from "@/shared/ui/EmptyState.vue";

type BoardSort = "latest" | "hot" | "top";
type TopicStatusFilter = "all" | "solved" | "unanswered" | "official";

// Loads board management controls only for owners/admins so regular board pages keep a smaller route chunk.
// Key parameters: none. Return value is the BoardSettingsPanel component; side effect is lazy chunk loading.
const BoardSettingsPanel = defineAsyncComponent(() =>
  import("@/features/boards/components/BoardSettingsPanel.vue"),
);

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
  </svg>`,
  "private-space": `<svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <rect x="13" y="28" width="38" height="28" rx="5" />
    <path d="M21 28v-8c0-7 4.9-12 11-12s11 5 11 12v8" />
    <circle cx="32" cy="41" r="3" />
    <path d="M32 44v5" />
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

const sortTabs: Array<{ key: BoardSort; label: string }> = [
  { key: "latest", label: "最新" },
  { key: "hot", label: "热门" },
  { key: "top", label: "精华" },
];

const statusFilters: Array<{ key: TopicStatusFilter; label: string }> = [
  { key: "all", label: "全部" },
  { key: "solved", label: "已解决" },
  { key: "unanswered", label: "未回复" },
  { key: "official", label: "官方回复" },
];
const answerFilterBoardSlugs = new Set(["qna", "questions", "support"]);

const route = useRoute();
const router = useRouter();

const slug = computed(() => readRouteParam(route.params.slug));
const currentUserQuery = useCurrentUser();
const siteSettingsQuery = usePublicSiteSettings();
const boardQuery = useBoardDetail(slug);
const board = computed(() => boardQuery.data.value);
const siteTitle = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "site_title", "平行线"),
);
useSeoMeta(
  computed(() =>
    board.value
      ? {
          title: `${board.value.name} · ${siteTitle.value}`,
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
const canDeleteTopics = computed(() => isAdmin(currentUserQuery.data.value));
const { deletingTopicId, requestDeleteTopic } = useAdminTopicDelete({
  note: "前台版块列表管理员删除主题。",
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

// showAnswerFilters 用途：仅问答/支持类版块显示解答状态筛选；无参数，返回布尔值且无副作用。
const showAnswerFilters = computed(() => answerFilterBoardSlugs.has(slug.value));
const topicsQuery = useBoardTopics(slug, activeSort);
// hasSidebar 用途：判断当前版块页是否需要右侧管理/子版块栏；无参数，返回布尔值且无副作用。
const hasSidebar = computed(() => Boolean(board.value?.childBoards.length) || canManageBoard.value);

const allBoardTopics = computed(() => topicsQuery.data.value ?? board.value?.latestTopics ?? []);

// sortedBoardTopics 用途：按当前排序组织版块主题，并始终让置顶帖优先展示；无参数，返回排序后的列表且不修改源数据。
const sortedBoardTopics = computed(() => {
  const list = [...allBoardTopics.value];

  if (activeSort.value === "hot") {
    list.sort((left, right) => right.hotScore - left.hotScore);
  } else if (activeSort.value === "top") {
    list.sort((left, right) => right.likeCount + right.replyCount - (left.likeCount + left.replyCount));
  } else {
    list.sort((left, right) => Date.parse(right.lastPostedAt) - Date.parse(left.lastPostedAt));
  }

  return list.sort((left, right) => Number(right.pinned) - Number(left.pinned));
});

const boardTopics = computed(() => {
  const keyword = searchQuery.value.trim().toLocaleLowerCase();

  return sortedBoardTopics.value.filter((topic) => {
    const matchesKeyword = keyword
      ? `${topic.title} ${topic.excerpt} ${topic.tags.join(" ")}`.toLocaleLowerCase().includes(keyword)
      : true;
    const matchesStatus =
      !showAnswerFilters.value ||
      activeStatus.value === "all" ||
      (activeStatus.value === "solved" && topic.solved) ||
      (activeStatus.value === "unanswered" && topic.replyCount === 0) ||
      (activeStatus.value === "official" && topic.officialReply);

    return matchesKeyword && matchesStatus;
  });
});

// searchPlaceholder 用途：根据版块类型生成主题搜索框提示；无参数，返回展示文案且无副作用。
const searchPlaceholder = computed(() => {
  if (showAnswerFilters.value) {
    return "搜索问题、错误码或日志片段";
  }

  return "搜索主题标题或标签";
});
// emptyTopicDescription 用途：根据搜索和发帖权限生成空列表提示；无参数，返回展示文案且无副作用。
const emptyTopicDescription = computed(() => {
  if (searchQuery.value) {
    return "换个关键词再搜，或清除搜索查看全部主题。";
  }

  return board.value?.canCreateTopic ? "发布第一篇主题，或稍后再来看看。" : "稍后再来看看。";
});

// boardMark 用途：生成单字版块徽标兜底，避免多字在方形标记中换行溢出；无副作用。
function boardMark(name: string) {
  return name.trim().slice(0, 1) || "版";
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
            <div class="board-title-row">
              <RouterLink class="board-title-row__parent" to="/boards">全部版块</RouterLink>
              <span class="board-title-row__separator">/</span>
              <h1 id="board-title">{{ board.name }}</h1>
            </div>
          </div>
        </div>

      </section>

      <div class="board-layout" :class="[boardToneClass(board.slug), { 'board-layout--single': !hasSidebar }]">
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

              <div v-if="showAnswerFilters" class="status-filters" aria-label="解答状态">
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

          <UiCard v-if="topicsQuery.isError.value" class="board-state board-state--error" role="alert">
            主题列表暂时加载失败，请稍后刷新。
          </UiCard>
          <TopicList
            :topics="boardTopics"
            empty-title="还没有主题"
            :empty-description="emptyTopicDescription"
            :can-delete-topics="canDeleteTopics"
            :deleting-topic-id="deletingTopicId"
            @delete-topic="requestDeleteTopic"
          />
          <RouterLink
            v-if="!topicsQuery.isLoading.value && !boardTopics.length && !searchQuery && board.canCreateTopic"
            class="board-empty-publish-link"
            :to="{ name: 'new-topic', query: { board: board.slug } }"
          >
            在此版块发帖
          </RouterLink>
        </main>

        <aside v-if="hasSidebar" class="board-sidebar" aria-label="版块信息">
          <UiCard v-if="board.childBoards.length" class="sidebar-panel child-board-panel">
            <span class="panel-kicker">子版块</span>
            <h2>相关版块</h2>
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
        </aside>
      </div>
    </template>

    <UiEmptyState v-else title="没有找到这个版块" description="可能是链接已变更，回到版块目录重新选择。">
      <RouterLink class="empty-link" to="/boards">返回版块目录</RouterLink>
    </UiEmptyState>
  </div>
</template>

<style scoped lang="scss" src="./BoardPage.scss"></style>
