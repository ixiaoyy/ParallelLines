<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ArrowLeftOutlined,
  FireOutlined,
  HeartFilled,
  HeartOutlined,
  LinkOutlined,
  MessageOutlined,
  RocketOutlined,
  StarFilled,
  StarOutlined,
} from "@ant-design/icons-vue";

import type { InteractionStateResponse } from "@/features/interactions/model";
import { setTopicBookmark, setTopicLike } from "@/features/interactions/api";
import type {
  ImmersiveTopicFeedItemVM,
  ImmersiveTopicFeedSort,
  ImmersiveTopicFeedParams,
} from "@/features/topics/model";
import { toImmersiveTopicFeedItem } from "@/features/topics/model";
import { useImmersiveTopicFeed, useMarkTopicReadState } from "@/features/topics/queries";
import { hasAccessToken, resolveApiAssetUrl } from "@/shared/api/client";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import { readRouteParam } from "@/shared/router/params";
import { topicDetailRoute } from "@/shared/router/topicRoutes";

interface FeedTopicInteractionState {
  liked: boolean;
  likeCount: number;
  bookmarked: boolean;
  bookmarkCount: number;
  reactionEmoji: string | null;
}

const route = useRoute();
const router = useRouter();
const viewportRef = ref<HTMLElement | null>(null);
const activeIndex = ref(0);
const touchStartX = ref(0);
const touchStartY = ref(0);
const lastWheelNavigationAt = ref(0);
const locallyReadTopicIds = ref<Set<string>>(new Set());
const interactionOverrides = ref<Record<string, FeedTopicInteractionState>>({});
const pendingLikeTopicIds = ref<Set<string>>(new Set());
const pendingBookmarkTopicIds = ref<Set<string>>(new Set());
const reactionMenuTopicId = ref<string | null>(null);
const feedActionStatus = ref("");
let readTimer: number | null = null;

const sortOptions: Array<{ value: ImmersiveTopicFeedSort; label: string }> = [
  { value: "latest", label: "最新" },
  { value: "recommended", label: "推荐" },
  { value: "hot", label: "热门" },
  { value: "top", label: "精华" },
];
const reactionOptions: Array<{ emoji: string; label: string }> = [
  { emoji: "❤️", label: "喜欢" },
  { emoji: "👍", label: "赞同" },
  { emoji: "😆", label: "好笑" },
  { emoji: "😮", label: "惊讶" },
  { emoji: "👏", label: "鼓掌" },
  { emoji: "🤯", label: "震撼" },
  { emoji: "🤗", label: "暖心" },
  { emoji: "🙄", label: "无语" },
  { emoji: "😭", label: "泪目" },
  { emoji: "🐱", label: "有趣" },
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

// Returns the locally optimistic interaction state for one feed item.
// Key parameter `item` is the visible feed item. Return value combines server
// fields with local overrides. Side effect: none.
function topicInteractionState(item: ImmersiveTopicFeedItemVM): FeedTopicInteractionState {
  return interactionOverrides.value[item.topic.id] ?? {
    liked: item.topic.likedByMe,
    likeCount: item.topic.likeCount,
    bookmarked: item.topic.bookmarkedByMe,
    bookmarkCount: item.topic.bookmarkCount,
    reactionEmoji: item.topic.likedByMe ? "❤️" : null,
  };
}

// Stores an immutable local interaction override for one topic.
// Key parameters are the topic id and next state. Return value is none. Side
// effect: replaces `interactionOverrides`.
function setTopicInteractionState(topicId: string, nextState: FeedTopicInteractionState) {
  interactionOverrides.value = {
    ...interactionOverrides.value,
    [topicId]: nextState,
  };
}

// Toggles whether the reaction picker is open for a feed item.
// Key parameter `item` is the topic whose reaction menu should open. Return
// value is none. Side effect: updates local menu state.
function toggleReactionMenu(item: ImmersiveTopicFeedItemVM) {
  reactionMenuTopicId.value = reactionMenuTopicId.value === item.topic.id ? null : item.topic.id;
}

// Applies a visual reaction and persists it as the existing topic-like action.
// Key parameters are the feed item and selected emoji. Return value resolves
// after the API request. Side effects: optimistic like state and status text.
async function applyFeedReaction(item: ImmersiveTopicFeedItemVM, emoji: string) {
  const current = topicInteractionState(item);
  const nextLiked = !(current.liked && current.reactionEmoji === emoji);
  await commitFeedLike(item, nextLiked, nextLiked ? emoji : null);
  reactionMenuTopicId.value = null;
}

// Toggles the default heart reaction for a feed item.
// Key parameter `item` is the topic being liked/unliked. Return value resolves
// after the API request. Side effects: optimistic like state and status text.
async function toggleFeedLike(item: ImmersiveTopicFeedItemVM) {
  const current = topicInteractionState(item);
  await commitFeedLike(item, !current.liked, current.liked ? null : "❤️");
}

// Persists the topic-like state while keeping the reading feed responsive.
// Key parameters are the feed item, target active state, and optional emoji.
// Return value resolves after the API request. Side effects: optimistic state,
// pending flags, and status copy.
async function commitFeedLike(
  item: ImmersiveTopicFeedItemVM,
  nextLiked: boolean,
  reactionEmoji: string | null,
) {
  const topicId = item.topic.id;
  if (pendingLikeTopicIds.value.has(topicId)) {
    return;
  }
  if (!hasAccessToken()) {
    feedActionStatus.value = "登录后可以给帖子点赞。";
    return;
  }

  const current = topicInteractionState(item);
  const optimisticState = {
    ...current,
    liked: nextLiked,
    likeCount: Math.max(0, current.likeCount + (nextLiked === current.liked ? 0 : nextLiked ? 1 : -1)),
    reactionEmoji,
  };
  setTopicInteractionState(topicId, optimisticState);
  pendingLikeTopicIds.value = new Set([...pendingLikeTopicIds.value, topicId]);
  try {
    const response = await setTopicLike(topicId, nextLiked);
    setTopicInteractionState(topicId, interactionStateFromLikeResponse(optimisticState, response));
    feedActionStatus.value = nextLiked ? "已记录反应。" : "已取消反应。";
  } catch {
    setTopicInteractionState(topicId, current);
    feedActionStatus.value = "点赞失败，请稍后重试。";
  } finally {
    const nextPending = new Set(pendingLikeTopicIds.value);
    nextPending.delete(topicId);
    pendingLikeTopicIds.value = nextPending;
  }
}

// Merges the backend like response into the local feed interaction state.
// Key parameters are the optimistic state and API response. Return value is the
// next local state. Side effect: none.
function interactionStateFromLikeResponse(
  current: FeedTopicInteractionState,
  response: InteractionStateResponse,
): FeedTopicInteractionState {
  return {
    ...current,
    liked: response.active,
    likeCount: response.count,
    reactionEmoji: response.active ? current.reactionEmoji ?? "❤️" : null,
  };
}

// Toggles topic bookmark state from the reading dock.
// Key parameter `item` is the topic being bookmarked. Return value resolves
// after the API request. Side effects: optimistic bookmark state and status.
async function toggleFeedBookmark(item: ImmersiveTopicFeedItemVM) {
  const topicId = item.topic.id;
  if (pendingBookmarkTopicIds.value.has(topicId)) {
    return;
  }
  if (!hasAccessToken()) {
    feedActionStatus.value = "登录后可以收藏帖子。";
    return;
  }

  const current = topicInteractionState(item);
  const nextBookmarked = !current.bookmarked;
  setTopicInteractionState(topicId, {
    ...current,
    bookmarked: nextBookmarked,
    bookmarkCount: Math.max(0, current.bookmarkCount + (nextBookmarked ? 1 : -1)),
  });
  pendingBookmarkTopicIds.value = new Set([...pendingBookmarkTopicIds.value, topicId]);
  try {
    const response = await setTopicBookmark(topicId, nextBookmarked);
    setTopicInteractionState(topicId, {
      ...topicInteractionState(item),
      bookmarked: response.active,
      bookmarkCount: response.count,
    });
    feedActionStatus.value = nextBookmarked ? "已收藏。" : "已取消收藏。";
  } catch {
    setTopicInteractionState(topicId, current);
    feedActionStatus.value = "收藏失败，请稍后重试。";
  } finally {
    const nextPending = new Set(pendingBookmarkTopicIds.value);
    nextPending.delete(topicId);
    pendingBookmarkTopicIds.value = nextPending;
  }
}

// Copies the current topic URL while staying inside reading mode.
// Key parameter `item` is the topic whose share link is copied. Return value
// resolves after clipboard work. Side effect: updates status text.
async function copyFeedTopicLink(item: ImmersiveTopicFeedItemVM) {
  const fallbackPath = router.resolve(topicDetailRoute({ id: item.topic.id, slug: item.topic.slug })).href;
  const shareUrl = item.topic.shareUrl || `${window.location.origin}${fallbackPath}`;
  try {
    await navigator.clipboard.writeText(shareUrl);
    feedActionStatus.value = "已复制帖子链接。";
  } catch {
    feedActionStatus.value = "无法访问剪贴板，请从详情页复制。";
  }
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

          <footer class="immersive-action-dock" aria-label="阅读操作">
            <div
              v-if="reactionMenuTopicId === item.topic.id"
              class="immersive-reaction-menu"
              role="menu"
              aria-label="选择反应"
            >
              <button
                v-for="reaction in reactionOptions"
                :key="reaction.emoji"
                type="button"
                :aria-label="reaction.label"
                :class="{ active: topicInteractionState(item).reactionEmoji === reaction.emoji }"
                @click="applyFeedReaction(item, reaction.emoji)"
              >
                {{ reaction.emoji }}
              </button>
            </div>

            <button
              type="button"
              class="immersive-action-button immersive-action-button--primary"
              :class="{ active: topicInteractionState(item).liked }"
              :disabled="pendingLikeTopicIds.has(item.topic.id)"
              aria-label="反应"
              @click="toggleReactionMenu(item)"
            >
              <span class="immersive-action-button__emoji">
                {{ topicInteractionState(item).reactionEmoji ?? "♡" }}
              </span>
              <small>{{ compactNumber(topicInteractionState(item).likeCount) }}</small>
            </button>
            <button
              type="button"
              class="immersive-action-button"
              :class="{ active: topicInteractionState(item).liked }"
              :disabled="pendingLikeTopicIds.has(item.topic.id)"
              aria-label="点赞"
              @click="toggleFeedLike(item)"
            >
              <HeartFilled v-if="topicInteractionState(item).liked" />
              <HeartOutlined v-else />
            </button>
            <button
              type="button"
              class="immersive-action-button"
              :class="{ active: topicInteractionState(item).bookmarked }"
              :disabled="pendingBookmarkTopicIds.has(item.topic.id)"
              aria-label="收藏"
              @click="toggleFeedBookmark(item)"
            >
              <StarFilled v-if="topicInteractionState(item).bookmarked" />
              <StarOutlined v-else />
            </button>
            <button type="button" class="immersive-action-button" aria-label="复制链接" @click="copyFeedTopicLink(item)">
              <LinkOutlined />
            </button>
            <button type="button" class="immersive-action-button" aria-label="查看评论" @click="openTopicDetail(item)">
              <MessageOutlined />
              <small>{{ compactNumber(item.topic.replyCount) }}</small>
            </button>
            <button type="button" class="immersive-action-button" aria-label="下一条" @click="navigateBy(1)">
              <RocketOutlined />
            </button>
          </footer>
        </article>
      </div>
    </main>
    <p v-if="feedActionStatus" class="immersive-action-status" role="status">{{ feedActionStatus }}</p>
  </div>
</template>

<style scoped lang="scss" src="./ImmersiveFeedPage.scss"></style>
