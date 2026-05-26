<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import type { TopicCardVM } from "@/entities/topic/model";
import { useBoards } from "@/features/boards/queries";
import { useTags } from "@/features/tags/queries";
import type { TopicSort } from "@/features/topics/model";
import { useTopicFeed } from "@/features/topics/queries";
import HomeCategoryGrid from "@/pages/home/components/HomeCategoryGrid.vue";
import HomeFoundingPost from "@/pages/home/components/HomeFoundingPost.vue";
import HomeHero from "@/pages/home/components/HomeHero.vue";
import HomeLeftRail from "@/pages/home/components/HomeLeftRail.vue";
import HomeSectionHead from "@/pages/home/components/HomeSectionHead.vue";
import HomeSidebar from "@/pages/home/components/HomeSidebar.vue";
import HomeTopicFeed from "@/pages/home/components/HomeTopicFeed.vue";
import { discoveryTabs, type DiscoveryTab } from "@/pages/home/discovery";

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

const boardSummaries = computed(() => boardsQuery.data.value ?? []);
const feedTopics = computed(() => topicsQuery.data.value ?? []);
const qualityPostKeywords = ["论坛初衷", "社区规范"];

const isNamedQualityPost = (topic: TopicCardVM) =>
  qualityPostKeywords.some(
    (keyword) => topic.title.includes(keyword) || topic.tags.includes(keyword),
  );

const qualityPostRank = (topic: TopicCardVM) => {
  const rank = qualityPostKeywords.findIndex(
    (keyword) => topic.title.includes(keyword) || topic.tags.includes(keyword),
  );

  return rank === -1 ? qualityPostKeywords.length : rank;
};

const pinnedQualityTopics = computed(() => {
  const preferred = feedTopics.value.filter(isNamedQualityPost).sort((left, right) => {
    return qualityPostRank(left) - qualityPostRank(right);
  });
  const pinnedFeatured = feedTopics.value.filter((topic) => topic.pinned && topic.featured);

  return [...preferred, ...pinnedFeatured].filter(
    (topic, index, topics) => topics.findIndex((candidate) => candidate.id === topic.id) === index,
  );
});
const discoveryTopics = computed(() =>
  feedTopics.value.filter(
    (topic) => !pinnedQualityTopics.value.some((qualityTopic) => qualityTopic.id === topic.id),
  ),
);
const topBoards = computed(() => boardSummaries.value.slice(0, 4));
const railBoards = computed(() => boardSummaries.value.slice(0, 8));
const topTags = computed(() => (tagsQuery.data.value ?? []).slice(0, 10));

const hotTopics = computed(() =>
  [...discoveryTopics.value].sort((left, right) => right.hotScore - left.hotScore).slice(0, 4),
);

const visibleTopics = computed(() => {
  const sorted = [...discoveryTopics.value];

  if (activeTab.value === "top") {
    return sorted.sort((left, right) => right.likeCount + right.replyCount - (left.likeCount + left.replyCount));
  }

  if (activeTab.value === "hot") {
    return sorted.sort((left, right) => right.hotScore - left.hotScore);
  }

  if (activeTab.value === "votes") {
    return sorted.sort((left, right) => right.likeCount - left.likeCount);
  }

  if (activeTab.value === "categories") {
    return sorted.sort((left, right) => left.boardName.localeCompare(right.boardName));
  }

  return sorted;
});

watch(
  () => route.hash,
  (hash) => {
    if (hash === "#hot") {
      activeTab.value = "hot";
      return;
    }

    if (hash === "#votes") {
      activeTab.value = "votes";
      return;
    }

    if (hash === "#solved") {
      activeTab.value = "top";
    }
  },
  { immediate: true },
);

function setActiveTab(tabKey: DiscoveryTab["key"]) {
  activeTab.value = tabKey;
}

function submitHeroSearch() {
  const q = heroSearch.value.trim();
  if (!q) {
    return;
  }

  void router.push({ name: "search", query: { q } });
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
        <HomeFoundingPost
          v-if="pinnedQualityTopics.length"
          class="founding-post-slot"
          :topics="pinnedQualityTopics"
        />

        <HomeSectionHead
          id="category-title"
          class="category-head"
          title="推荐分类"
          mobile-title="其他板块"
          description="用少量、明确的入口降低浏览压力。"
          link-label="查看全部分类"
          :link-to="{ name: 'board-directory' }"
        />
        <HomeCategoryGrid
          class="category-grid-slot"
          :boards="topBoards"
          :loading="boardsQuery.isLoading.value"
          :error="boardsQuery.isError.value"
        />

        <HomeSectionHead
          id="feed-title"
          class="feed-head"
          title="最新讨论"
          description="列表保持克制：主题、摘要、标签、回复、浏览、动态。"
          feed
        />
        <HomeTopicFeed
          class="feed-slot"
          :tabs="discoveryTabs"
          :active-tab="activeTab"
          :topics="visibleTopics"
          :loading="topicsQuery.isLoading.value"
          :error="topicsQuery.isError.value"
          @select-tab="setActiveTab"
        />
      </main>

      <HomeSidebar
        :hot-topics="hotTopics"
        :tags="topTags"
        :topics-loading="topicsQuery.isLoading.value"
        :topics-error="topicsQuery.isError.value"
        :tags-loading="tagsQuery.isLoading.value"
        :tags-error="tagsQuery.isError.value"
      />
    </div>
  </div>
</template>

<style scoped lang="scss" src="./HomePage.scss"></style>
