<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

import type { BoardSummary } from "@/entities/board/model";
import { sortBoardsWithFeedbackLast } from "@/entities/board/order";
import type { TopicCardVM } from "@/entities/topic/model";
import type { TagItemVM } from "@/features/tags/model";
import HomeTopicRow from "@/pages/home/components/HomeTopicRow.vue";
import type { DiscoveryTab } from "@/pages/home/discovery";

const props = defineProps<{
  tabs: DiscoveryTab[];
  activeTab: DiscoveryTab["key"];
  topics: TopicCardVM[];
  totalTopics: number;
  boards: BoardSummary[];
  tags: TagItemVM[];
  titleFilter: string;
  boardFilter: string;
  tagFilter: string;
  loading: boolean;
  error: boolean;
}>();

const emit = defineEmits<{
  selectTab: [tabKey: DiscoveryTab["key"]];
  updateTitleFilter: [value: string];
  updateBoardFilter: [value: string];
  updateTagFilter: [value: string];
  clearFilters: [];
}>();

const displayLimit = ref(5);
const infiniteScrollActive = ref(false);
const filtersOpen = ref(false);
const scrollTriggerRef = ref<HTMLElement | null>(null);
const slicedTopics = computed(() => props.topics.slice(0, displayLimit.value));
const hasActiveFilters = computed(() =>
  Boolean(props.titleFilter.trim() || props.boardFilter.trim() || props.tagFilter.trim()),
);
const filteredSummary = computed(() => {
  if (!hasActiveFilters.value) {
    return `${props.totalTopics} 个主题`;
  }

  return `${props.topics.length}/${props.totalTopics} 个主题`;
});
const boardOptions = computed(() =>
  sortBoardsWithFeedbackLast(props.boards, (left, right) => left.name.localeCompare(right.name, "zh-Hans-CN")),
);
const tagOptions = computed(() => props.tags.map((tag) => tag.name));
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
    if (active) {
      filtersOpen.value = true;
    }
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
      <button
        type="button"
        class="filter-link"
        :class="{ active: hasActiveFilters }"
        :aria-expanded="filtersOpen"
        aria-controls="topic-feed-filters"
        @click="filtersOpen = !filtersOpen"
      >
        过滤帖子
        <span>{{ filteredSummary }}</span>
      </button>
    </div>

    <div v-show="filtersOpen" id="topic-feed-filters" class="topic-filter-panel" aria-label="帖子过滤">
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
        <span>板块</span>
        <select :value="boardFilter" @change="emit('updateBoardFilter', ($event.target as HTMLSelectElement).value)">
          <option value="">全部板块</option>
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

    <p v-if="loading" class="panel-state" role="status">正在加载主题…</p>
    <p v-else-if="error" class="panel-state panel-state--error" role="alert">暂时无法加载主题，请稍后刷新。</p>
    <p v-else-if="!topics.length" class="panel-state">暂无主题。</p>
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
