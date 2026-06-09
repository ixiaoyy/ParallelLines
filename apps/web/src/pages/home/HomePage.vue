<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { LocationQueryRaw } from "vue-router";

import type { TopicCardVM } from "@/entities/topic/model";
import { publicSettingString } from "@/features/admin/model";
import { usePublicSiteSettings } from "@/features/admin/queries";
import { useBoards } from "@/features/boards/queries";
import { useTags } from "@/features/tags/queries";
import type { TopicSort } from "@/features/topics/model";
import { useTopicFeed } from "@/features/topics/queries";
import HomeHero from "@/pages/home/components/HomeHero.vue";
import HomeTopicFeed from "@/pages/home/components/HomeTopicFeed.vue";
import { discoveryTabs, type DiscoveryTab } from "@/pages/home/discovery";
import {
  cacheHomeRailBoards,
  cacheHomeRailTags,
  cacheHomeFeedTopics,
  readCachedHomeRailBoards,
  readCachedHomeRailTags,
  readCachedHomeFeedTopics,
} from "@/pages/home/homeRailCache";
import { readRouteParam } from "@/shared/router/params";
import { useMediaQuery } from "@/shared/lib/useMediaQuery";
import { useSeoMeta } from "@/shared/seo/meta";

// Defers desktop-only rail icons and markup so mobile first paint does not download hidden navigation.
// Key parameters: none. Return value is the HomeLeftRail component; side effect is lazy chunk loading on desktop.
const HomeLeftRail = defineAsyncComponent(() => import("@/pages/home/components/HomeLeftRail.vue"));

const activeTab = ref<DiscoveryTab["key"]>("latest");
const heroSearch = ref("");
const router = useRouter();
const route = useRoute();
const isDesktopRailVisible = useMediaQuery("(min-width: 981px)", true);
const filtersDataRequested = ref(false);
const siteSettingsQuery = usePublicSiteSettings();

const feedSort = computed<TopicSort>(() =>
  activeTab.value === "hot" ? "hot" : activeTab.value === "top" ? "top" : "latest",
);
const topicsQuery = useTopicFeed(feedSort);
const cachedRailBoards = ref(readCachedHomeRailBoards());
const cachedRailTags = ref(readCachedHomeRailTags());
const cachedFeedTopics = ref<Record<TopicSort, TopicCardVM[]>>({
  latest: readCachedHomeFeedTopics("latest"),
  hot: readCachedHomeFeedTopics("hot"),
  top: readCachedHomeFeedTopics("top"),
  votes: readCachedHomeFeedTopics("votes"),
});

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
const shouldLoadTaxonomy = computed(() =>
  isDesktopRailVisible.value ||
  filtersDataRequested.value ||
  Boolean(titleFilter.value.trim() || boardFilter.value.trim() || tagFilter.value.trim()),
);
const boardsQuery = useBoards(shouldLoadTaxonomy);
const tagsQuery = useTags(30, shouldLoadTaxonomy);
const boardSummaries = computed(() => boardsQuery.data.value ?? []);
const feedTopics = computed(() => {
  if (topicsQuery.data.value) {
    return topicsQuery.data.value;
  }

  return topicsQuery.isLoading.value ? cachedFeedTopics.value[feedSort.value] : [];
});
const discoveryTopics = computed(() =>
  feedTopics.value.filter((topic) => !(topic.pinned && topic.title === `关于「${topic.boardName}」`)),
);
const filteredTopics = computed(() =>
  discoveryTopics.value.filter((topic) =>
    matchesTitleFilter(topic) && matchesBoardFilter(topic) && matchesTagFilter(topic),
  ),
);
const railBoards = computed(() => {
  if (boardsQuery.data.value) {
    return boardSummaries.value;
  }

  return boardsQuery.isLoading.value ? cachedRailBoards.value : [];
});
const topTags = computed(() => {
  const tags = tagsQuery.data.value;
  if (tags) {
    return tags.slice(0, 10);
  }

  return tagsQuery.isLoading.value ? cachedRailTags.value : [];
});
const railBoardsLoading = computed(
  () => boardsQuery.isLoading.value && cachedRailBoards.value.length === 0,
);
const railTagsLoading = computed(
  () => tagsQuery.isLoading.value && cachedRailTags.value.length === 0,
);
const topicFeedLoading = computed(
  () => topicsQuery.isLoading.value && cachedFeedTopics.value[feedSort.value].length === 0,
);
const siteTitle = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "site_title", "平行线"),
);
const siteDescription = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "site_tagline", "让答案可追溯"),
);

useSeoMeta(
  computed(() => ({
    title: siteTitle.value,
    description: siteDescription.value,
    canonicalPath: "/",
  })),
);

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

watch(
  () => titleFilter.value,
  (value) => {
    heroSearch.value = value;
  },
  { immediate: true },
);

watch(
  () => boardsQuery.data.value,
  (boards) => {
    if (boards) {
      cachedRailBoards.value = cacheHomeRailBoards(boards);
    }
  },
  { immediate: true },
);

watch(
  () => tagsQuery.data.value,
  (tags) => {
    if (tags) {
      cachedRailTags.value = cacheHomeRailTags(tags);
    }
  },
  { immediate: true },
);

watch(
  () => [feedSort.value, topicsQuery.data.value] as const,
  ([sort, topics]) => {
    if (topics) {
      cachedFeedTopics.value = {
        ...cachedFeedTopics.value,
        [sort]: cacheHomeFeedTopics(sort, topics),
      };
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

// Applies the hero search to the real home feed title filter and scrolls to the filtered results.
// Key parameters: none; it reads `heroSearch`. Side effect: updates URL query state and moves the viewport to the feed.
function submitHeroSearch() {
  const q = heroSearch.value.trim();
  if (!q) {
    return;
  }

  titleFilter.value = q;
  void nextTick(() => {
    document.getElementById("topic-feed")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
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
        v-if="isDesktopRailVisible"
        :boards="railBoards"
        :tags="topTags"
        :boards-loading="railBoardsLoading"
        :boards-error="boardsQuery.isError.value"
        :tags-loading="railTagsLoading"
        :tags-error="tagsQuery.isError.value"
      />

      <main class="main-column" aria-label="平行线首页内容">
        <HomeHero
          v-model:search="heroSearch"
          class="home-hero-slot"
          @submit-search="submitHeroSearch"
        />

        <HomeTopicFeed
          id="topic-feed"
          class="feed-slot"
          :tabs="discoveryTabs"
          :active-tab="activeTab"
          :topics="visibleTopics"
          :boards="boardSummaries"
          :tags="topTags"
          :title-filter="titleFilter"
          :board-filter="boardFilter"
          :tag-filter="tagFilter"
          :loading="topicFeedLoading"
          :error="topicsQuery.isError.value"
          @select-tab="setActiveTab"
          @update-title-filter="setTitleFilter"
          @update-board-filter="setBoardFilter"
          @update-tag-filter="setTagFilter"
          @filters-visibility-change="filtersDataRequested = filtersDataRequested || $event"
          @clear-filters="clearTopicFilters"
        />
      </main>

    </div>
  </div>
</template>

<style scoped lang="scss" src="./HomePage.scss"></style>
