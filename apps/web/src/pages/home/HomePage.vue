<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { LocationQueryRaw } from "vue-router";

import type { TopicCardVM } from "@/entities/topic/model";
import { useBoards } from "@/features/boards/queries";
import { useTags } from "@/features/tags/queries";
import type { TopicSort } from "@/features/topics/model";
import { useTopicFeed } from "@/features/topics/queries";
import HomeHero from "@/pages/home/components/HomeHero.vue";
import HomeLeftRail from "@/pages/home/components/HomeLeftRail.vue";
import HomeTopicFeed from "@/pages/home/components/HomeTopicFeed.vue";
import { discoveryTabs, type DiscoveryTab } from "@/pages/home/discovery";
import { readRouteParam } from "@/shared/router/params";

const activeTab = ref<DiscoveryTab["key"]>("latest");
const heroSearch = ref("");
const router = useRouter();
const route = useRoute();

const feedSort = computed<TopicSort>(() =>
  activeTab.value === "hot" ? "hot" : activeTab.value === "top" ? "top" : "latest",
);
const boardsQuery = useBoards();
const topicsQuery = useTopicFeed(feedSort);
const tagsQuery = useTags(30);

const titleFilter = computed({
  get: () => readRouteParam(route.query.title as string | string[] | undefined),
  set: (value: string) => updateFilterQuery("title", value),
});
const boardFilter = computed({
  get: () => readRouteParam(route.query.board as string | string[] | undefined),
  set: (value: string) => updateFilterQuery("board", value),
});
const tagFilter = computed({
  get: () => readRouteParam(route.query.tag as string | string[] | undefined),
  set: (value: string) => updateFilterQuery("tag", value),
});
const boardSummaries = computed(() => boardsQuery.data.value ?? []);
const feedTopics = computed(() => topicsQuery.data.value ?? []);
const discoveryTopics = computed(() =>
  feedTopics.value.filter((topic) => !(topic.pinned && topic.title === `关于「${topic.boardName}」`)),
);
const filteredTopics = computed(() =>
  discoveryTopics.value.filter((topic) =>
    matchesTitleFilter(topic) && matchesBoardFilter(topic) && matchesTagFilter(topic),
  ),
);
const railBoards = computed(() => boardSummaries.value);
const topTags = computed(() => (tagsQuery.data.value ?? []).slice(0, 10));

const visibleTopics = computed(() => {
  const sorted = [...filteredTopics.value];

  if (activeTab.value === "top") {
    return sorted.sort((left, right) => right.likeCount + right.replyCount - (left.likeCount + left.replyCount));
  }

  if (activeTab.value === "hot") {
    return sorted.sort((left, right) => right.hotScore - left.hotScore);
  }

  return sorted.sort((left, right) => right.lastPostedAt.localeCompare(left.lastPostedAt));
});

watch(
  () => route.hash,
  (hash) => {
    if (hash === "#hot") {
      activeTab.value = "hot";
      return;
    }

    if (hash === "#featured" || hash === "#solved") {
      activeTab.value = "top";
    }
  },
  { immediate: true },
);

function setActiveTab(tabKey: DiscoveryTab["key"]) {
  activeTab.value = tabKey;
}

function setTitleFilter(value: string) {
  titleFilter.value = value;
}

function setBoardFilter(value: string) {
  boardFilter.value = value;
}

function setTagFilter(value: string) {
  tagFilter.value = value;
}

function clearTopicFilters() {
  void router.replace({
    name: "home",
    query: omitEmptyQuery({
      ...route.query,
      title: undefined,
      board: undefined,
      tag: undefined,
    }),
    hash: route.hash,
  });
}

function submitHeroSearch() {
  const q = heroSearch.value.trim();
  if (!q) {
    return;
  }

  void router.push({ name: "search", query: { q } });
}

function updateFilterQuery(key: "title" | "board" | "tag", value: string) {
  void router.replace({
    name: "home",
    query: omitEmptyQuery({
      ...route.query,
      [key]: value.trim() || undefined,
    }),
    hash: route.hash,
  });
}

function matchesTitleFilter(topic: TopicCardVM) {
  const keyword = normalizeFilter(titleFilter.value);
  return !keyword || normalizeFilter(topic.title).includes(keyword);
}

function matchesBoardFilter(topic: TopicCardVM) {
  const board = normalizeFilter(boardFilter.value);
  if (!board) {
    return true;
  }

  return normalizeFilter(topic.boardSlug) === board || normalizeFilter(topic.boardName) === board;
}

function matchesTagFilter(topic: TopicCardVM) {
  const tag = normalizeFilter(tagFilter.value);
  return !tag || topic.tags.some((topicTag) => normalizeFilter(topicTag) === tag);
}

function normalizeFilter(value: string) {
  return value.trim().toLocaleLowerCase();
}

function omitEmptyQuery(query: Record<string, unknown>): LocationQueryRaw {
  return Object.fromEntries(
    Object.entries(query).filter(([, value]) => value !== undefined && value !== ""),
  ) as LocationQueryRaw;
}
</script>

<template>
  <div id="top" class="forum-home">
    <div class="home-grid">
      <HomeLeftRail
        :boards="railBoards"
        :tags="topTags"
        :boards-loading="boardsQuery.isLoading.value"
        :boards-error="boardsQuery.isError.value"
        :tags-loading="tagsQuery.isLoading.value"
        :tags-error="tagsQuery.isError.value"
      />

      <main class="main-column" aria-label="平行线首页内容">
        <HomeHero
          v-model:search="heroSearch"
          class="home-hero-slot"
          @submit-search="submitHeroSearch"
        />

        <HomeTopicFeed
          class="feed-slot"
          :tabs="discoveryTabs"
          :active-tab="activeTab"
          :topics="visibleTopics"
          :total-topics="discoveryTopics.length"
          :boards="boardSummaries"
          :tags="topTags"
          :title-filter="titleFilter"
          :board-filter="boardFilter"
          :tag-filter="tagFilter"
          :loading="topicsQuery.isLoading.value"
          :error="topicsQuery.isError.value"
          @select-tab="setActiveTab"
          @update-title-filter="setTitleFilter"
          @update-board-filter="setBoardFilter"
          @update-tag-filter="setTagFilter"
          @clear-filters="clearTopicFilters"
        />
      </main>

    </div>
  </div>
</template>

<style scoped lang="scss" src="./HomePage.scss"></style>
