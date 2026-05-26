<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import type { TopicCardVM } from "@/entities/topic/model";
import { useBoards } from "@/features/boards/queries";
import { useTags } from "@/features/tags/queries";
import type { TopicSort } from "@/features/topics/model";
import { useTopicFeed } from "@/features/topics/queries";
import HomeFoundingPost from "@/pages/home/components/HomeFoundingPost.vue";
import HomeHero from "@/pages/home/components/HomeHero.vue";
import HomeLeftRail from "@/pages/home/components/HomeLeftRail.vue";
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
const communityGuideKeywords = ["论坛初衷", "社区规范"];

const isCommunityGuideTopic = (topic: TopicCardVM) =>
  communityGuideKeywords.some(
    (keyword) => topic.title.includes(keyword) || topic.tags.includes(keyword),
  );

const communityGuideRank = (topic: TopicCardVM) => {
  const rank = communityGuideKeywords.findIndex(
    (keyword) => topic.title.includes(keyword) || topic.tags.includes(keyword),
  );

  return rank === -1 ? communityGuideKeywords.length : rank;
};

const communityGuideTopics = computed(() => {
  return feedTopics.value.filter(isCommunityGuideTopic).sort((left, right) => {
    return communityGuideRank(left) - communityGuideRank(right);
  });
});
const discoveryTopics = computed(() => feedTopics.value);
const railBoards = computed(() => boardSummaries.value.slice(0, 8));
const topTags = computed(() => (tagsQuery.data.value ?? []).slice(0, 10));

const visibleTopics = computed(() => {
  const sorted = [...discoveryTopics.value];

  if (activeTab.value === "top") {
    return sortPinnedFirst(
      sorted,
      (left, right) => right.likeCount + right.replyCount - (left.likeCount + left.replyCount),
    );
  }

  if (activeTab.value === "hot") {
    return sortPinnedFirst(sorted, (left, right) => right.hotScore - left.hotScore);
  }

  if (activeTab.value === "votes") {
    return sortPinnedFirst(sorted, (left, right) => right.likeCount - left.likeCount);
  }

  return sortPinnedFirst(sorted, (left, right) => right.lastPostedAt.localeCompare(left.lastPostedAt));
});

function sortPinnedFirst(
  topics: TopicCardVM[],
  compare: (left: TopicCardVM, right: TopicCardVM) => number,
) {
  return topics.sort((left, right) => Number(right.pinned) - Number(left.pinned) || compare(left, right));
}

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
          v-if="communityGuideTopics.length"
          class="founding-post-slot"
          :topics="communityGuideTopics"
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

    </div>
  </div>
</template>

<style scoped lang="scss" src="./HomePage.scss"></style>
