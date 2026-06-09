<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ArrowLeftOutlined,
  EyeOutlined,
  FireOutlined,
  HeartOutlined,
  MessageOutlined,
} from "@ant-design/icons-vue";

import type {
  ImmersiveTopicFeedItemVM,
  ImmersiveTopicFeedSort,
  ImmersiveTopicFeedParams,
} from "@/features/topics/model";
import { toImmersiveTopicFeedItem } from "@/features/topics/model";
import { useImmersiveTopicFeed, useMarkTopicReadState } from "@/features/topics/queries";
import { hasAccessToken, resolveApiAssetUrl } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
import { readRouteParam } from "@/shared/router/params";
import { topicDetailRoute } from "@/shared/router/topicRoutes";

const route = useRoute();
const router = useRouter();
const viewportRef = ref<HTMLElement | null>(null);
const activeIndex = ref(0);
const touchStartX = ref(0);
const touchStartY = ref(0);
const lastWheelNavigationAt = ref(0);
const locallyReadTopicIds = ref<Set<string>>(new Set());
let readTimer: number | null = null;

const sortOptions: Array<{ value: ImmersiveTopicFeedSort; label: string }> = [
  { value: "latest", label: "最新" },
  { value: "recommended", label: "推荐" },
  { value: "hot", label: "热门" },
  { value: "top", label: "精华" },
];

const feedParams = computed<Omit<ImmersiveTopicFeedParams, "cursor">>(() => ({
  sort: parseFeedSort(route.query.sort),
  board: routeTextParam(route.query.board),
  tag: routeTextParam(route.query.tag),
  q: routeTextParam(route.query.q || route.query.title),
  limit: 12,
}));
const feedQuery = useImmersiveTopicFeed(feedParams);
const markReadMutation = useMarkTopicReadState();
const feedItems = computed<ImmersiveTopicFeedItemVM[]>(() =>
  (feedQuery.data.value?.pages ?? [])
    .flatMap((page) => page.items)
    .map(toImmersiveTopicFeedItem),
);
const activeItem = computed(() => feedItems.value[activeIndex.value] ?? null);
const activeSort = computed(() => feedParams.value.sort ?? "latest");
const feedTitle = computed(() => {
  if (feedParams.value.q) {
    return `搜索：${feedParams.value.q}`;
  }
  if (feedParams.value.tag) {
    return `标签：${feedParams.value.tag}`;
  }
  if (feedParams.value.board) {
    return `版块：${feedParams.value.board}`;
  }
  return "沉浸阅读";
});
const trackStyle = computed(() => ({
  transform: `translate3d(0, -${activeIndex.value * 100}dvh, 0)`,
}));

watch(
  () => feedParams.value,
  () => {
    activeIndex.value = 0;
  },
);

watch(
  activeItem,
  (item) => {
    scheduleActiveTopicRead(item);
  },
  { immediate: true },
);

watch(activeIndex, () => {
  void fetchNextPageNearEnd();
});

// Parses the route sort query into the limited immersive feed sort set.
// Key parameter `value` is a Vue route query value. Return value is a safe sort.
// Side effect: none.
function parseFeedSort(value: unknown): ImmersiveTopicFeedSort {
  const sort = readRouteParam(value as string | string[] | undefined);
  return sortOptions.some((option) => option.value === sort)
    ? (sort as ImmersiveTopicFeedSort)
    : "latest";
}

// Reads a string route query parameter and trims empty values to undefined.
// Key parameter `value` is a Vue route query value. Return value is a filter
// string or undefined. Side effect: none.
function routeTextParam(value: unknown): string | undefined {
  const text = readRouteParam(value as string | string[] | undefined).trim();
  return text || undefined;
}

// Updates the route sort query while preserving active board/tag/search filters.
// Key parameter `sort` is the selected feed mode. Return value is none. Side
// effect: replaces the current route query.
function updateSort(sort: ImmersiveTopicFeedSort) {
  void router.replace({
    name: "immersive-feed",
    query: {
      ...route.query,
      sort,
    },
  });
}

// Navigates back to the previous page, falling back to home when history is empty.
// Key parameters: none. Return value is none. Side effect: changes router state.
function leaveFeed() {
  if (window.history.length > 1) {
    router.back();
    return;
  }
  void router.push({ name: "home" });
}

// Opens the current feed item in the normal topic detail page.
// Key parameter `item` is a feed card. Return value is none. Side effect:
// pushes a topic detail route.
function openTopicDetail(item: ImmersiveTopicFeedItemVM) {
  void router.push(topicDetailRoute({ id: item.topic.id, slug: item.topic.slug }));
}

// Moves the full-screen feed up or down by one item.
// Key parameter `delta` is `1` for next and `-1` for previous. Return value is
// none. Side effect: updates active index or requests the next cursor page.
function navigateBy(delta: 1 | -1) {
  const nextIndex = activeIndex.value + delta;
  if (nextIndex >= 0 && nextIndex < feedItems.value.length) {
    activeIndex.value = nextIndex;
    return;
  }
  if (delta > 0) {
    void fetchNextPageNearEnd();
  }
}

// Handles wheel gestures while allowing long post bodies to scroll first.
// Key parameter `event` is the wheel event. Return value is none. Side effect:
// may prevent default scrolling and change active item.
function handleWheel(event: WheelEvent) {
  const direction = event.deltaY > 0 ? 1 : -1;
  if (canActiveBodyScroll(direction)) {
    return;
  }

  event.preventDefault();
  const now = Date.now();
  if (now - lastWheelNavigationAt.value < 520) {
    return;
  }
  lastWheelNavigationAt.value = now;
  navigateBy(direction > 0 ? 1 : -1);
}

// Records touch start coordinates for vertical swipe detection.
// Key parameter `event` is the touch event. Return value is none. Side effect:
// stores the first touch position.
function handleTouchStart(event: TouchEvent) {
  const touch = event.touches[0];
  if (!touch) {
    return;
  }
  touchStartX.value = touch.clientX;
  touchStartY.value = touch.clientY;
}

// Converts touch release into feed navigation after scroll-conflict checks.
// Key parameter `event` is the touch event. Return value is none. Side effect:
// may change the active feed item.
function handleTouchEnd(event: TouchEvent) {
  const touch = event.changedTouches[0];
  if (!touch) {
    return;
  }
  const deltaX = touch.clientX - touchStartX.value;
  const deltaY = touch.clientY - touchStartY.value;
  if (Math.abs(deltaY) < 52 || Math.abs(deltaY) < Math.abs(deltaX) * 1.25) {
    return;
  }

  const direction = deltaY < 0 ? 1 : -1;
  if (canActiveBodyScroll(direction)) {
    return;
  }
  navigateBy(direction > 0 ? 1 : -1);
}

// Checks whether the active post body can continue scrolling in a direction.
// Key parameter `direction` is positive for downward content scroll. Return
// value is boolean. Side effect: none.
function canActiveBodyScroll(direction: number) {
  const body = activeScrollableBody();
  if (!body) {
    return false;
  }
  if (direction > 0) {
    return body.scrollTop + body.clientHeight < body.scrollHeight - 2;
  }
  return body.scrollTop > 2;
}

// Finds the scrollable body for the active slide.
// Key parameters: none. Return value is the active body element or null. Side
// effect: reads from the DOM only.
function activeScrollableBody() {
  return viewportRef.value?.querySelector<HTMLElement>(
    ".immersive-slide--active [data-feed-scrollable='true']",
  ) ?? null;
}

// Prefetches the next cursor page when the user nears the loaded tail.
// Key parameters: none. Return value resolves after any fetch request. Side
// effect: may request another feed page.
async function fetchNextPageNearEnd() {
  if (
    activeIndex.value < feedItems.value.length - 3 ||
    !feedQuery.hasNextPage.value ||
    feedQuery.isFetchingNextPage.value
  ) {
    return;
  }
  await feedQuery.fetchNextPage();
}

// Schedules read-state persistence for the active topic after a short dwell.
// Key parameter `item` is the active feed item. Return value is none. Side
// effect: starts or clears a timer and may mutate backend read state.
function scheduleActiveTopicRead(item: ImmersiveTopicFeedItemVM | null) {
  if (readTimer) {
    window.clearTimeout(readTimer);
    readTimer = null;
  }
  if (!item || !hasAccessToken() || item.readState.read || locallyReadTopicIds.value.has(item.topic.id)) {
    return;
  }

  readTimer = window.setTimeout(() => {
    markReadMutation.mutate({
      topicId: item.topic.id,
      payload: { last_read_post_number: item.readState.highest_post_number },
    });
    locallyReadTopicIds.value = new Set([...locallyReadTopicIds.value, item.topic.id]);
  }, 650);
}

// Returns safe display HTML for a feed item body.
// Key parameter `item` is a feed card. Return value is backend-rendered HTML
// when available, otherwise an escaped excerpt paragraph. Side effect: none.
function feedBodyHtml(item: ImmersiveTopicFeedItemVM) {
  return item.leadPost?.cookedHtml
    ? resolvedMarkdownHtml(item.leadPost.cookedHtml)
    : `<p>${escapeHtml(item.topic.excerpt)}</p>`;
}

// Resolves API-relative image and link URLs inside backend-rendered Markdown.
// Key parameter `html` is trusted backend-rendered post HTML. Return value is
// browser-ready HTML. Side effect: none outside a temporary template element.
function resolvedMarkdownHtml(html: string) {
  if (!html || typeof document === "undefined") {
    return html;
  }

  const template = document.createElement("template");
  template.innerHTML = html;
  template.content.querySelectorAll<HTMLImageElement>("img").forEach((image) => {
    const resolved = resolveApiAssetUrl(image.getAttribute("src"));
    if (resolved) {
      image.src = resolved;
    }
  });
  template.content.querySelectorAll<HTMLAnchorElement>("a").forEach((anchor) => {
    const resolved = resolveApiAssetUrl(anchor.getAttribute("href"));
    if (resolved) {
      anchor.href = resolved;
    }
  });
  return template.innerHTML;
}

// Escapes plain text before it is used in a v-html fallback paragraph.
// Key parameter `value` is arbitrary text. Return value is HTML-safe text.
// Side effect: none.
function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Returns whether a feed item has been read in the API payload or this session.
// Key parameter `item` is a feed card. Return value is boolean. Side effect:
// none.
function isRead(item: ImmersiveTopicFeedItemVM) {
  return item.readState.read || locallyReadTopicIds.value.has(item.topic.id);
}
</script>

<template>
  <div
    class="immersive-feed-page"
    @wheel="handleWheel"
    @touchstart.passive="handleTouchStart"
    @touchend.passive="handleTouchEnd"
  >
    <header class="immersive-feed-topbar">
      <button type="button" class="immersive-icon-button" aria-label="返回" @click="leaveFeed">
        <ArrowLeftOutlined />
      </button>
      <div class="immersive-feed-title">
        <strong>{{ feedTitle }}</strong>
        <span>{{ feedItems.length ? `${activeIndex + 1} / ${feedItems.length}` : "准备中" }}</span>
      </div>
      <nav class="immersive-sort-tabs" aria-label="信息流排序">
        <button
          v-for="option in sortOptions"
          :key="option.value"
          type="button"
          :class="{ active: activeSort === option.value }"
          @click="updateSort(option.value)"
        >
          {{ option.label }}
        </button>
      </nav>
    </header>

    <main ref="viewportRef" class="immersive-feed-viewport" aria-label="沉浸式帖子信息流">
      <div v-if="feedQuery.isLoading.value" class="immersive-feed-state" role="status">
        <FireOutlined />
        <strong>正在加载信息流</strong>
      </div>
      <div v-else-if="feedQuery.isError.value" class="immersive-feed-state immersive-feed-state--error" role="alert">
        <strong>信息流暂时不可用</strong>
        <button type="button" @click="feedQuery.refetch()">重试</button>
      </div>
      <div v-else-if="!feedItems.length" class="immersive-feed-state">
        <strong>没有可刷的帖子</strong>
        <RouterLink :to="{ name: 'home' }">返回首页</RouterLink>
      </div>
      <div v-else class="immersive-feed-track" :style="trackStyle">
        <article
          v-for="(item, index) in feedItems"
          :key="item.topic.id"
          class="immersive-slide"
          :class="{ 'immersive-slide--active': index === activeIndex }"
          :style="{ '--board-color': item.topic.boardColor }"
          :aria-hidden="index !== activeIndex"
        >
          <section class="immersive-slide__content">
            <div class="immersive-slide__meta">
              <span>{{ item.topic.boardName }}</span>
              <span>{{ relativeTime(item.topic.lastPostedAt) }}</span>
              <span v-if="isRead(item)">已读</span>
              <span v-else>未读 {{ item.readState.unread_count }}</span>
            </div>
            <h1>{{ item.topic.title }}</h1>
            <div class="immersive-slide__tags">
              <span v-for="tag in item.topic.tags" :key="tag">{{ tag }}</span>
            </div>
            <div
              class="immersive-slide__body markdown-body"
              data-feed-scrollable="true"
              v-html="feedBodyHtml(item)"
            />
          </section>

          <aside class="immersive-slide__rail" aria-label="帖子操作">
            <button type="button" @click="openTopicDetail(item)">
              <MessageOutlined />
              <span>{{ item.topic.replyCount }}</span>
            </button>
            <button type="button" @click="openTopicDetail(item)">
              <HeartOutlined />
              <span>{{ item.topic.likeCount }}</span>
            </button>
            <button type="button" @click="openTopicDetail(item)">
              <EyeOutlined />
              <span>{{ item.topic.viewCount }}</span>
            </button>
          </aside>

          <footer class="immersive-slide__footer">
            <div class="immersive-author">
              <img v-if="item.topic.authorAvatarUrl" :src="resolveApiAssetUrl(item.topic.authorAvatarUrl)" alt="" />
              <span v-else>{{ item.topic.authorName.slice(0, 1).toUpperCase() }}</span>
              <div>
                <strong>{{ item.topic.authorName }}</strong>
                <small>{{ item.topic.authorTrustLevelLabel }}</small>
              </div>
            </div>
            <button type="button" @click="navigateBy(1)">
              下一条
            </button>
          </footer>
        </article>
      </div>
    </main>
  </div>
</template>

<style scoped lang="scss" src="./ImmersiveFeedPage.scss"></style>
