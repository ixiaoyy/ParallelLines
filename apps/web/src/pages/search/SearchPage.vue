<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import TopicList from "@/features/topics/components/TopicList.vue";
import type { TopicSort } from "@/features/topics/model";
import { useTopicSearch } from "@/features/topics/queries";
import { readRouteParam } from "@/shared/router/params";
import UiBadge from "@/shared/ui/Badge.vue";
import UiCard from "@/shared/ui/Card.vue";

const route = useRoute();
const router = useRouter();

const q = computed({
  get: () => readRouteParam(route.query.q as string | string[] | undefined),
  set: (value: string) => {
    void router.replace({ name: "search", query: { ...route.query, q: value.trim() || undefined } });
  },
});

const activeSort = computed<TopicSort>({
  get: () => {
    const sort = readRouteParam(route.query.sort as string | string[] | undefined);
    return sort === "hot" || sort === "top" ? sort : "latest";
  },
  set: (value) => {
    void router.replace({
      name: "search",
      query: { ...route.query, sort: value === "latest" ? undefined : value },
    });
  },
});

const searchParams = computed(() => ({
  q: q.value,
  sort: activeSort.value,
  board: readRouteParam(route.query.board as string | string[] | undefined) || undefined,
  tag: readRouteParam(route.query.tag as string | string[] | undefined) || undefined,
  author: readRouteParam(route.query.author as string | string[] | undefined) || undefined,
}));

const searchQuery = useTopicSearch(searchParams);
const topics = computed(() => searchQuery.data.value ?? []);

const sortTabs: Array<{ key: TopicSort; label: string }> = [
  { key: "latest", label: "最新" },
  { key: "hot", label: "热门" },
  { key: "top", label: "高信号" },
];
</script>

<template>
  <div class="search-page">
    <section class="search-hero" aria-labelledby="search-title">
      <div>
        <UiBadge tone="blue">搜索</UiBadge>
        <h1 id="search-title">按错误码、接口名或正文线索查主题。</h1>
        <p>搜索会覆盖主题标题和楼层正文；也可以叠加版块、标签和作者过滤。</p>
      </div>

      <label class="search-input" for="search-page-input">
        <span>关键词</span>
        <input
          id="search-page-input"
          v-model="q"
          type="search"
          placeholder="例如：OIDC state mismatch、请求超时、Markdown"
          autocomplete="off"
        />
      </label>
    </section>

    <UiCard class="search-toolbar">
      <div>
        <span class="panel-kicker">结果</span>
        <strong>{{ q ? `“${q}”` : "等待输入关键词" }}</strong>
      </div>
      <div class="sort-tabs" aria-label="搜索排序">
        <button
          v-for="tab in sortTabs"
          :key="tab.key"
          type="button"
          :class="{ active: activeSort === tab.key }"
          @click="activeSort = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>
    </UiCard>

    <UiCard v-if="q && searchQuery.isError.value" class="search-error" role="alert">
      搜索暂时不可用，请稍后重试。
    </UiCard>
    <TopicList v-else-if="q" :topics="topics" />

    <UiCard v-else class="search-empty">
      <h2>先输入一个具体线索</h2>
      <p>优先搜索错误码、接口名、日志关键词，能更快定位已解决主题。</p>
      <RouterLink class="empty-link" :to="{ name: 'board-directory' }">
        还不确定？先看版块入口
      </RouterLink>
    </UiCard>
  </div>
</template>

<style scoped lang="scss" src="./SearchPage.scss"></style>
