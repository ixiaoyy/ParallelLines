<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

import type { BoardSummary } from "@/entities/board/model";
import { sortBoardsWithFeedbackLast } from "@/entities/board/order";
import type { TopicCardVM } from "@/entities/topic/model";
import type { TagItemVM } from "@/features/tags/model";
import HomeTopicRow from "@/pages/home/components/HomeTopicRow.vue";
import type { DiscoveryTab } from "@/pages/home/discovery";
import { relativeTime } from "@/shared/lib/format";
import { topicDetailRoute } from "@/shared/router/topicRoutes";

const props = defineProps<{
  tabs: DiscoveryTab[];
  activeTab: DiscoveryTab["key"];
  topics: TopicCardVM[];
  boards: BoardSummary[];
  tags: TagItemVM[];
  titleFilter: string;
  boardFilter: string;
  tagFilter: string;
  canPublishTopic: boolean;
  filtersOpen: boolean;
  loading: boolean;
  error: boolean;
}>();

const emit = defineEmits<{
  selectTab: [tabKey: DiscoveryTab["key"]];
  updateTitleFilter: [value: string];
  updateBoardFilter: [value: string];
  updateTagFilter: [value: string];
  updateFiltersOpen: [open: boolean];
  filtersVisibilityChange: [open: boolean];
  clearFilters: [];
}>();

const displayLimit = ref(5);
const infiniteScrollActive = ref(false);
const scrollTriggerRef = ref<HTMLElement | null>(null);
const slicedTopics = computed(() => props.topics.slice(0, displayLimit.value));
const hasActiveFilters = computed(() =>
  Boolean(props.titleFilter.trim() || props.boardFilter.trim() || props.tagFilter.trim()),
);
// Builds visitor-facing empty-state copy from the current filters; returns display text only and has no side effects.
const emptyTitle = computed(() => (hasActiveFilters.value ? "没有符合筛选的主题" : "还没有公开主题"));
const emptyDescription = computed(() =>
  hasActiveFilters.value
    ? "换一个标题、版块或标签条件，通常能更快找到相关线索。"
    : "从第一个真实问题开始，标题写清现象、环境和期望结果。",
);
const boardOptions = computed(() =>
  sortBoardsWithFeedbackLast(props.boards, (left, right) => left.name.localeCompare(right.name, "zh-Hans-CN")),
);
const tagOptions = computed(() => props.tags.map((tag) => tag.name));
const todayProgramTopic = computed(() => props.topics.find((topic) => isTodayProgram(topic)) ?? null);
const todayProgramTags = computed(() =>
  (todayProgramTopic.value?.tags ?? [])
    .filter((tag) => tag !== "今日节目" && tag !== "AI节目")
    .slice(0, 3),
);
let observer: IntersectionObserver | null = null;

function handleLoadMore() {
  displayLimit.value = Math.min(displayLimit.value + 5, props.topics.length);
  infiniteScrollActive.value = true;
}

function loadMoreOnScroll() {
  if (displayLimit.value < props.topics.length) {
    displayLimit.value = Math.min(displayLimit.value + 10, props.topics.length);
  }
}

function setupObserver() {
  observer?.disconnect();
  if (!infiniteScrollActive.value || !scrollTriggerRef.value) {
    return;
  }

  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting) {
        loadMoreOnScroll();
      }
    },
    { rootMargin: "150px" },
  );

  observer.observe(scrollTriggerRef.value);
}

// Requests the parent-owned filter panel visibility so the hero icon and feed panel stay synchronized.
// Key parameters: `open` is the desired panel state. Side effect: emits the requested state to HomePage.
function requestFiltersOpen(open: boolean) {
  emit("updateFiltersOpen", open);
}

// Detects AI-operated daily program topics from durable tags and local activity date.
// Key parameter: mapped topic card. Return value: true when the row should be promoted in today's home feed.
function isTodayProgram(topic: TopicCardVM) {
  return topic.tags.includes("今日节目") && isSameLocalDate(topic.lastPostedAt, new Date());
}

// Compares an ISO timestamp with the viewer's current local calendar day for lightweight home labeling.
function isSameLocalDate(value: string, now: Date) {
  const parsed = new Date(value);
  return (
    parsed.getFullYear() === now.getFullYear() &&
    parsed.getMonth() === now.getMonth() &&
    parsed.getDate() === now.getDate()
  );
}

watch([infiniteScrollActive, scrollTriggerRef], setupObserver);

watch(
  () => [props.activeTab, props.topics.length, props.titleFilter, props.boardFilter, props.tagFilter],
  () => {
    displayLimit.value = 5;
    infiniteScrollActive.value = false;
  },
);

watch(
  hasActiveFilters,
  (active) => {
    if (active && !props.filtersOpen) {
      requestFiltersOpen(true);
    }
  },
  { immediate: true },
);

watch(
  () => props.filtersOpen,
  (open) => {
    emit("filtersVisibilityChange", open);
  },
  { immediate: true },
);

onUnmounted(() => observer?.disconnect());
</script>

<template>
  <section class="home-topic-feed" aria-label="主题发现流">
    <div class="tabs">
      <div class="tab-list" role="tablist" aria-label="主题筛选">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab.key"
          :class="['tab', { active: activeTab === tab.key }]"
          @click="emit('selectTab', tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <section
      v-if="todayProgramTopic"
      class="daily-program"
      aria-labelledby="daily-program-title"
    >
      <div class="daily-program__copy">
        <span class="daily-program__kicker">今日 AI 在搞什么</span>
        <h2 id="daily-program-title">
          <RouterLink :to="topicDetailRoute(todayProgramTopic)">
            {{ todayProgramTopic.title }}
          </RouterLink>
        </h2>
        <p>{{ todayProgramTopic.excerpt }}</p>
        <div class="daily-program__meta">
          <span>{{ todayProgramTopic.authorName }}</span>
          <span>{{ relativeTime(todayProgramTopic.lastPostedAt) }}</span>
          <span v-for="tag in todayProgramTags" :key="tag">#{{ tag }}</span>
        </div>
      </div>
      <RouterLink class="daily-program__action" :to="topicDetailRoute(todayProgramTopic)">
        去看看
      </RouterLink>
    </section>

    <div v-if="filtersOpen" id="topic-feed-filters" class="topic-filter-panel" aria-label="主题过滤">
      <label class="topic-filter-field topic-filter-field--title">
        <span>标题关键词</span>
        <input
          :value="titleFilter"
          type="search"
          placeholder="只匹配标题"
          autocomplete="off"
          @input="emit('updateTitleFilter', ($event.target as HTMLInputElement).value)"
        />
      </label>

      <label class="topic-filter-field">
        <span>版块</span>
        <select :value="boardFilter" @change="emit('updateBoardFilter', ($event.target as HTMLSelectElement).value)">
          <option value="">全部版块</option>
          <option v-for="board in boardOptions" :key="board.id" :value="board.slug">
            {{ board.parentBoardName ? `${board.parentBoardName} / ` : "" }}{{ board.name }}
          </option>
        </select>
      </label>

      <label class="topic-filter-field">
        <span>标签</span>
        <input
          :value="tagFilter"
          list="topic-feed-tag-options"
          placeholder="全部标签"
          autocomplete="off"
          @input="emit('updateTagFilter', ($event.target as HTMLInputElement).value)"
        />
      </label>

      <button type="button" class="filter-clear-button" :disabled="!hasActiveFilters" @click="emit('clearFilters')">
        清空
      </button>
      <datalist id="topic-feed-tag-options">
        <option v-for="tag in tagOptions" :key="tag" :value="tag" />
      </datalist>
    </div>

    <div class="feed-header" aria-hidden="true">
      <span>主题</span>
      <span>回复</span>
      <span>浏览</span>
      <span>活动</span>
    </div>

    <div v-if="loading" class="feed-skeleton" role="status" aria-label="正在加载主题">
      <div v-for="item in 4" :key="item" class="skeleton-row" aria-hidden="true">
        <span class="skeleton-avatar"></span>
        <span class="skeleton-copy">
          <i></i>
          <b></b>
        </span>
        <span class="skeleton-metric"></span>
        <span class="skeleton-metric"></span>
        <span class="skeleton-activity"></span>
      </div>
    </div>
    <p v-else-if="error" class="panel-state panel-state--error" role="alert">暂时无法加载主题，请稍后刷新。</p>
    <div v-else-if="!topics.length" class="feed-empty">
      <strong>{{ emptyTitle }}</strong>
      <p>{{ emptyDescription }}</p>
      <div class="feed-empty__actions">
        <button v-if="hasActiveFilters" type="button" @click="emit('clearFilters')">清空筛选</button>
        <RouterLink v-if="canPublishTopic" :to="{ name: 'new-topic' }">发布主题</RouterLink>
        <RouterLink :to="{ name: 'board-directory' }">浏览版块</RouterLink>
      </div>
    </div>
    <template v-else>
      <HomeTopicRow v-for="topic in slicedTopics" :key="topic.id" :topic="topic" />

      <div class="feed-load-container">
        <div v-if="topics.length > displayLimit" class="load-more-action">
          <button class="btn-load-more" @click="handleLoadMore">显示全部主题 <span class="arrow">→</span></button>
        </div>
        <div v-if="infiniteScrollActive" ref="scrollTriggerRef" class="scroll-trigger">
          <div v-if="displayLimit < topics.length" class="loading-spinner">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
            正在加载更多...
          </div>
          <div v-else class="all-loaded">已显示全部主题</div>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped lang="scss" src="./HomeTopicFeed.scss"></style>
