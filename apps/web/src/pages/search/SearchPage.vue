<script setup lang="ts">
import { uiText } from "@/shared/i18n/locale";
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { isAdmin } from "@/features/auth/permissions";
import { useCurrentUser } from "@/features/auth/queries";
import TopicList from "@/features/topics/components/TopicList.vue";
import type { TopicSort } from "@/features/topics/model";
import { useTopicSearch } from "@/features/topics/queries";
import { useAdminTopicDelete } from "@/features/topics/useAdminTopicDelete";
import { useBoards } from "@/features/boards/queries";
import { readRouteParam } from "@/shared/router/params";
import UiBadge from "@/shared/ui/Badge.vue";
import UiCard from "@/shared/ui/Card.vue";

const route = useRoute();
const router = useRouter();
const currentUserQuery = useCurrentUser();

interface FilterChip {
  key: "board" | "tag" | "author";
  label: string;
  value: string;
}

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

const boardFilter = computed(() => readRouteParam(route.query.board as string | string[] | undefined));
const tagFilter = computed(() => readRouteParam(route.query.tag as string | string[] | undefined));
const authorFilter = computed(() => readRouteParam(route.query.author as string | string[] | undefined));
const boardsQuery = useBoards(computed(() => Boolean(boardFilter.value)));
const boardLabelBySlug = computed(() =>
  new Map((boardsQuery.data.value ?? []).map((board) => [board.slug, board.name])),
);

const searchParams = computed(() => ({
  q: q.value,
  sort: activeSort.value,
  board: boardFilter.value || undefined,
  tag: tagFilter.value || undefined,
  author: authorFilter.value || undefined,
}));

const searchQuery = useTopicSearch(searchParams);
const topics = computed(() => searchQuery.data.value ?? []);
const canDeleteTopics = computed(() => isAdmin(currentUserQuery.data.value));
const { deletingTopicId, requestDeleteTopic } = useAdminTopicDelete({
  note: "前台搜索列表管理员删除主题。",
});
const hasQuery = computed(() => Boolean(q.value.trim()));
const filterChips = computed<FilterChip[]>(() => {
  const chips: FilterChip[] = [];

  if (boardFilter.value) {
    chips.push({ key: "board", label: "版块", value: boardLabelBySlug.value.get(boardFilter.value) ?? boardFilter.value });
  }
  if (tagFilter.value) {
    chips.push({ key: "tag", label: "标签", value: tagFilter.value });
  }
  if (authorFilter.value) {
    chips.push({ key: "author", label: "作者", value: authorFilter.value });
  }

  return chips;
});
const hasFilters = computed(() => filterChips.value.length > 0);
const clearFiltersQuery = computed(() => ({
  q: q.value || undefined,
  sort: activeSort.value === "latest" ? undefined : activeSort.value,
}));
const resultSummary = computed(() => {
  if (!hasQuery.value) {
    return uiText("输入关键词开始搜索");
  }
  if (searchQuery.isFetching.value && !searchQuery.data.value) {
    return uiText("正在搜索 “{value0}”", { value0: q.value });
  }
  if (topics.value.length === 0) {
    return uiText("没有找到 “{value0}”", { value0: q.value });
  }
  return uiText("找到 {value0} 个相关主题", { value0: topics.value.length });
});
const emptyTitle = computed(() => (hasQuery.value ? "没有匹配结果" : "输入关键词开始搜索"));
const emptyDescription = computed(() =>
  hasQuery.value
    ? "换个关键词，或清除标签、版块、作者筛选后再试。"
    : "搜索会覆盖主题标题和楼层正文，也可以叠加标签、版块、作者过滤。",
);

const sortTabs: Array<{ key: TopicSort; label: string }> = [
  { key: "latest", label: "最新" },
  { key: "hot", label: "热门" },
  { key: "top", label: "精华" },
];
</script>

<template>
  <div class="search-page">
    <UiCard class="search-console">
      <section class="search-console__header" aria-labelledby="search-title">
        <div class="search-console__copy">
          <UiBadge tone="blue">{{ uiText("搜索") }}</UiBadge>
          <h1 id="search-title">{{ hasQuery ? uiText("搜索 “{value0}”", { value0: q }) : uiText("搜索社区内容") }}</h1>
          <p>{{ hasQuery ? uiText("按相关度和活跃度筛选主题，快速回到有用讨论。") : uiText("输入关键词后，可以继续按版块、标签或作者缩小范围。") }}</p>
        </div>

        <label class="search-input" for="search-page-input">
          <span>{{ uiText("关键词") }}</span>
          <input
            id="search-page-input"
            v-model="q"
            type="search"
            :placeholder="uiText('搜索主题、标签、作者')"
            autocomplete="off"
          />
        </label>
      </section>

      <div class="search-console__meta">
        <div class="result-heading">
          <span class="panel-kicker">{{ uiText("结果") }}</span>
          <strong>{{ resultSummary }}</strong>
        </div>

        <div class="sort-tabs" :aria-label="uiText('搜索排序')">
          <button
            v-for="tab in sortTabs"
            :key="tab.key"
            type="button"
            :class="{ active: activeSort === tab.key }"
            @click="activeSort = tab.key"
          >
            {{ uiText(tab.label) }}
          </button>
        </div>
      </div>

      <div v-if="hasFilters" class="filter-strip" :aria-label="uiText('当前筛选')">
        <span v-for="chip in filterChips" :key="chip.key" class="filter-chip">
          {{ uiText(chip.label) }}：{{ chip.value }}
        </span>
        <RouterLink class="filter-clear" :to="{ name: 'search', query: clearFiltersQuery }">
          {{ uiText("清除筛选") }}
        </RouterLink>
      </div>
    </UiCard>

    <UiCard v-if="hasQuery && searchQuery.isError.value" class="search-state search-state--error" role="alert">
      <strong>{{ uiText("搜索暂时不可用") }}</strong>
      <span>{{ uiText("请稍后重试，或先返回版块目录浏览内容。") }}</span>
    </UiCard>

    <UiCard v-else-if="hasQuery && searchQuery.isLoading.value" class="search-state">
      <strong>{{ uiText("正在搜索…") }}</strong>
      <span>{{ uiText("正在整理相关主题。") }}</span>
    </UiCard>

    <TopicList
      v-else-if="hasQuery && topics.length"
      :topics="topics"
      :can-delete-topics="canDeleteTopics"
      :deleting-topic-id="deletingTopicId"
      @delete-topic="requestDeleteTopic"
    />

    <UiCard v-else class="search-state search-state--empty">
      <strong>{{ uiText(emptyTitle) }}</strong>
      <span>{{ uiText(emptyDescription) }}</span>
      <RouterLink class="empty-link" :to="{ name: 'board-directory' }">
        {{ uiText("浏览全部版块") }}
      </RouterLink>
    </UiCard>
  </div>
</template>

<style scoped lang="scss" src="./SearchPage.scss"></style>
