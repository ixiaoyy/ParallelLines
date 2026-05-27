<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useBoards } from "@/features/boards/queries";
import { useTags } from "@/features/tags/queries";
import type { TopicSort } from "@/features/topics/model";
import { useTopicFeed } from "@/features/topics/queries";
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
const discoveryTopics = computed(() =>
  feedTopics.value.filter((topic) => !(topic.pinned && topic.title === `关于「${topic.boardName}」`)),
);
const railBoards = computed(() => boardSummaries.value.slice(0, 8));
const topTags = computed(() => (tagsQuery.data.value ?? []).slice(0, 10));

const visibleTopics = computed(() => {
  const sorted = [...discoveryTopics.value];

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
