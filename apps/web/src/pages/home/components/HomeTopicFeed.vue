<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

import type { TopicCardVM } from "@/entities/topic/model";
import HomeTopicRow from "@/pages/home/components/HomeTopicRow.vue";
import type { DiscoveryTab } from "@/pages/home/discovery";

const props = defineProps<{
  tabs: DiscoveryTab[];
  activeTab: DiscoveryTab["key"];
  topics: TopicCardVM[];
  loading: boolean;
  error: boolean;
}>();

const emit = defineEmits<{
  selectTab: [tabKey: DiscoveryTab["key"]];
}>();

const displayLimit = ref(5);
const infiniteScrollActive = ref(false);
const scrollTriggerRef = ref<HTMLElement | null>(null);
const slicedTopics = computed(() => props.topics.slice(0, displayLimit.value));
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
  () => [props.activeTab, props.topics.length],
  () => {
    displayLimit.value = 5;
    infiniteScrollActive.value = false;
  },
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
      <RouterLink class="filter-link" :to="{ name: 'board-directory' }">筛选分类</RouterLink>
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
