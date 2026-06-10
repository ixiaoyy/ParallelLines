<script setup lang="ts">
import { useMutation, useQueryClient } from "@tanstack/vue-query";
import { message } from "ant-design-vue";
import { computed, defineAsyncComponent, nextTick, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import type { PostItemVM } from "@/entities/post/model";
import { publicSettingString } from "@/features/admin/model";
import { usePublicSiteSettings } from "@/features/admin/queries";
import { useCurrentUser } from "@/features/auth/queries";
import { setTopicBookmark, setTopicLike } from "@/features/interactions/api";
import { useOptimisticToggle } from "@/features/interactions/useOptimisticToggle";
import { useContentModerationMutation, useCreateFlag } from "@/features/moderation/queries";
import type { NotificationLevel } from "@/features/notifications/model";
import {
  useTopicNotificationLevel,
  useUpdateTopicNotificationLevel,
} from "@/features/notifications/queries";
import type { PostSort } from "@/features/posts/api";
import PostItem from "@/features/posts/components/PostItem.vue";
import { useCreatePost, useTopicPosts } from "@/features/posts/queries";
import { setUserRelationship } from "@/features/social/api";
import TopicRepliesPanel from "@/features/topics/components/TopicRepliesPanel.vue";
import TopicDetailHero from "@/features/topics/components/TopicDetailHero.vue";
import TopicSwipeNavigator from "@/features/topics/components/TopicSwipeNavigator.vue";
import TopicThreadToolbar from "@/features/topics/components/TopicThreadToolbar.vue";
import {
  useBoardTopics,
  useMoveTopic,
  useSetTopicSolution,
  useTopicDetail,
  useTopicLifecycle,
  useVotePoll,
} from "@/features/topics/queries";
import { hasAccessToken } from "@/shared/api/client";
import { contentPolicyMessage } from "@/shared/api/errors";
import { queryKeys } from "@/shared/api/queryKeys";
import { compactNumber } from "@/shared/lib/format";
import { useMediaQuery } from "@/shared/lib/useMediaQuery";
import { readRouteParam } from "@/shared/router/params";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import { useSeoMeta } from "@/shared/seo/meta";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";
import UiEmptyState from "@/shared/ui/EmptyState.vue";

const COMIC_READER_TAG = "漫画阅读";

// Loads the reply composer only when the desktop bottom composer is visible or a mobile user opens it.
// Key parameters: none. Return value is the ComposerDrawer component; side effect is deferred editor-shell loading.
const ComposerDrawer = defineAsyncComponent(() => import("@/features/topics/components/ComposerDrawer.vue"));

// Loads poll UI only for topics that actually contain a poll.
// Key parameters: none. Return value is the PollPanel component; side effect is deferred poll chunk loading.
const PollPanel = defineAsyncComponent(() => import("@/features/topics/components/PollPanel.vue"));

// Loads report dialog only when the user opens the report flow.
// Key parameters: none. Return value is the ReportModal component; side effect is deferred moderation dialog loading.
const ReportModal = defineAsyncComponent(() => import("@/features/moderation/components/ReportModal.vue"));

// Loads the desktop/tablet side rail only when it can be shown.
// Key parameters: none. Return value is the TopicDetailSidebar component; side effect is deferred side-rail loading.
const TopicDetailSidebar = defineAsyncComponent(() => import("@/features/topics/components/TopicDetailSidebar.vue"));

const route = useRoute();
const router = useRouter();
const queryClient = useQueryClient();

const topicId = computed(() => readRouteParam(route.params.id));
const postSort = ref<PostSort>("chronological");
const topicQuery = useTopicDetail(topicId);
const postsQuery = useTopicPosts(topicId, postSort);
const createPost = useCreatePost(topicId);
const currentUserQuery = useCurrentUser();
const siteSettingsQuery = usePublicSiteSettings();
const topicNotificationQuery = useTopicNotificationLevel(topicId);
const updateTopicNotificationMutation = useUpdateTopicNotificationLevel(topicId);
const topic = computed(() => topicQuery.data.value);
const siteTitle = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "site_title", "平行线"),
);
const isDesktopReplyComposer = useMediaQuery("(min-width: 721px)", true);
const isDetailSidebarVisible = useMediaQuery("(min-width: 1121px)", true);
useSeoMeta(
  computed(() =>
    topic.value
      ? {
          title: `${topic.value.title} · ${topic.value.boardName} · ${siteTitle.value}`,
          description:
            topic.value.excerpt || `${topic.value.boardName} 中的公开主题：${topic.value.title}`,
          canonicalPath: `/topics/${topic.value.id}/${topic.value.slug}`,
          ogType: "article",
        }
      : null,
  ),
);
const posts = computed(() => postsQuery.data.value ?? []);
const onlyAuthor = ref(false);
const toolbarStatus = ref("");
const replyStatus = ref("");
const replyResetToken = ref(0);
const replyComposerOpen = ref(false);
const repliesExpanded = ref(false);
const replyInsertText = ref("");
const replyInsertToken = ref(0);
const topicSwipeStart = ref<{ x: number; y: number } | null>(null);
const currentUserId = computed(() => currentUserQuery.data.value?.id ?? null);
const currentUserRole = computed(() => currentUserQuery.data.value?.role ?? null);
const comicReader = computed(() => topic.value?.tags.includes(COMIC_READER_TAG) ?? false);
const canManageTopic = computed(
  () => currentUserRole.value === "admin" || currentUserRole.value === "moderator",
);
const canManageSolution = computed(
  () => Boolean(topic.value && currentUserId.value && currentUserId.value === topic.value.authorId) || canManageTopic.value,
);
const qaSort = computed(() => postSort.value === "qa");
const displayedPosts = computed(() => {
  if (!onlyAuthor.value || !topic.value) {
    return posts.value;
  }

  return posts.value.filter((post) => post.userId === topic.value?.authorId);
});
const firstPost = computed(() => displayedPosts.value.find((post) => post.floor === 1) ?? displayedPosts.value[0] ?? null);
const replyPosts = computed(() => displayedPosts.value.filter((post) => post.id !== firstPost.value?.id));
const hiddenRelationshipPostCount = computed(() => {
  const expectedPostCount = (topic.value?.replyCount ?? 0) + (topic.value ? 1 : 0);
  return Math.max(0, expectedPostCount - posts.value.length);
});
const shouldRenderReplyComposer = computed(() =>
  topic.value?.status === "open" && (isDesktopReplyComposer.value || replyComposerOpen.value),
);
const boardSwipeTopicsQuery = useBoardTopics(() => topic.value?.boardSlug ?? "", "latest");
const boardSwipeTopics = computed(() => boardSwipeTopicsQuery.data.value ?? []);
const relatedTopics = computed(() =>
  boardSwipeTopics.value
    .filter((candidate) => candidate.id !== topic.value?.id)
    .slice(0, 3),
);
const currentSwipeTopicIndex = computed(() =>
  boardSwipeTopics.value.findIndex((candidate) => candidate.id === topic.value?.id),
);
const previousSwipeTopic = computed(() => {
  const index = currentSwipeTopicIndex.value;
  return index > 0 ? boardSwipeTopics.value[index - 1] : null;
});
const nextSwipeTopic = computed(() => {
  const index = currentSwipeTopicIndex.value;
  return index >= 0 && index < boardSwipeTopics.value.length - 1 ? boardSwipeTopics.value[index + 1] : null;
});
const flagTopicMutation = useCreateFlag();
const topicModerationMutation = useContentModerationMutation({ awaitInvalidation: false });
const lifecycleMutation = useTopicLifecycle(topicId);
const moveTopicMutation = useMoveTopic(topicId);
const solutionMutation = useSetTopicSolution(topicId);
const pollVoteMutation = useVotePoll(topicId);
const blockAuthorMutation = useMutation({
  mutationFn: (username: string) => setUserRelationship(username, "block", true),
  onSuccess: (response) => {
    queryClient.setQueryData(queryKeys.userRelationship(response.target_username), response);
    void queryClient.invalidateQueries({ queryKey: queryKeys.posts(topicId.value) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.topic(topicId.value) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.topics("feed:latest") });
    void queryClient.invalidateQueries({ queryKey: queryKeys.topics("feed:hot") });
    void queryClient.invalidateQueries({ queryKey: queryKeys.topics("feed:top") });
    void queryClient.invalidateQueries({ queryKey: queryKeys.userTopics(response.target_username) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.notifications });
  },
});
const canFlagTopic = computed(() => Boolean(topic.value?.id) && hasAccessToken());
const flagTopicPending = computed(() => flagTopicMutation.isPending.value);
const deleteTopicPending = computed(() => topicModerationMutation.isPending.value);
const reportModalOpen = ref(false);
const topicNotificationLevel = computed<NotificationLevel>(
  () => topicNotificationQuery.data.value?.notification_level ?? "normal",
);
const topicNotificationPending = computed(
  () => topicNotificationQuery.isFetching.value || updateTopicNotificationMutation.isPending.value,
);
const canSetTopicNotification = computed(() => Boolean(topic.value?.id) && hasAccessToken());
const TOPIC_HORIZONTAL_SWIPE_MIN_PX = 72;
const TOPIC_HORIZONTAL_SWIPE_RATIO = 1.35;
const lifecyclePending = computed(
  () =>
    lifecycleMutation.isPending.value ||
    moveTopicMutation.isPending.value,
);
const {
  active: bookmarked,
  count: bookmarkCount,
  pending: bookmarkPending,
  toggle: toggleBookmark,
} = useOptimisticToggle({
  active: () => Boolean(topic.value?.bookmarkedByMe),
  count: () => topic.value?.bookmarkCount ?? 0,
  enabled: hasAccessToken,
  commit: async (active) => {
    const response = await setTopicBookmark(topic.value?.id ?? "", active);
    void queryClient.invalidateQueries({ queryKey: queryKeys.topic(topic.value?.id ?? "") });
    return response;
  },
  readActive: (response) => response.active,
  readCount: (response) => response.count,
  onDisabled: () => requireLogin("请先登录后再收藏主题。"),
  mockWhenDisabled: false,
});
const {
  active: topicLiked,
  count: topicLikeCount,
  pending: topicLikePending,
  toggle: toggleTopicLike,
} = useOptimisticToggle({
  active: () => Boolean(topic.value?.likedByMe),
  count: () => topic.value?.likeCount ?? 0,
  enabled: hasAccessToken,
  commit: async (active) => {
    const response = await setTopicLike(topic.value?.id ?? "", active);
    void queryClient.invalidateQueries({ queryKey: queryKeys.topic(topic.value?.id ?? "") });
    void queryClient.invalidateQueries({ queryKey: queryKeys.topics("feed:hot") });
    void queryClient.invalidateQueries({ queryKey: queryKeys.topics("feed:top") });
    return response;
  },
  readActive: (response) => response.active,
  readCount: (response) => response.count,
  onDisabled: () => requireLogin("请先登录后再点赞主题。"),
  mockWhenDisabled: false,
});

const topicStats = computed(() => {
  if (!topic.value) {
    return [];
  }

  return [
    { label: "回复", value: compactNumber(topic.value.replyCount) },
    { label: "浏览", value: compactNumber(topic.value.viewCount) },
    { label: "赞同", value: compactNumber(topicLikeCount.value) },
    { label: "收藏", value: compactNumber(bookmarkCount.value) },
  ];
});

watch(
  topic,
  (current) => {
    if (!current || route.name !== "topic-detail") {
      return;
    }

    const currentRouteSlug = readRouteParam(route.params.slug);
    if (currentRouteSlug === current.slug) {
      return;
    }

    void router.replace({
      ...topicDetailRoute(current),
      query: route.query,
      hash: route.hash,
    });
  },
  { immediate: true },
);

watch(
  () => [topicId.value, route.hash] as const,
  ([, hash]) => {
    if (shouldExpandRepliesForHash(hash)) {
      repliesExpanded.value = true;
      void scrollHashIntoViewAfterRepliesRender(hash);
      return;
    }

    repliesExpanded.value = false;
  },
  { immediate: true },
);

function handleReply(rawMd: string) {
  replyStatus.value = "";
  if (topic.value?.status !== "open") {
    replyStatus.value = "主题当前不可回复，草稿已保留。";
    return;
  }
  if (!hasAccessToken()) {
    replyStatus.value = "请先登录后再发布回复，草稿已保留。";
    void router.push({ name: "auth", query: { redirect: route.fullPath } });
    return;
  }

  createPost.mutate(
    { raw_md: rawMd },
    {
      onSuccess: () => {
        replyResetToken.value += 1;
        replyStatus.value = "回复已发布。";
      },
      onError: (error) => {
        replyStatus.value = contentPolicyMessage(
          error,
          "回复发布失败，请登录后重试；草稿已保留。",
        );
      },
    },
  );
}

function requireLogin(message: string) {
  setToolbarStatus(message);
  void router.push({ name: "auth", query: { redirect: route.fullPath } });
}

function setTopicStatus(status: "open" | "closed") {
  lifecycleMutation.mutate(
    { status, note: "从主题页工具栏更新状态" },
    {
      onSuccess: () => setToolbarStatus(status === "open" ? "主题已重新打开" : "主题已关闭"),
      onError: () => setToolbarStatus("主题状态更新失败，请确认权限"),
    },
  );
}

function toggleTopicPinned() {
  if (!topic.value) {
    return;
  }

  lifecycleMutation.mutate(
    { pinned: !topic.value.pinned, note: "从主题页工具栏更新置顶" },
    {
      onSuccess: () => setToolbarStatus(topic.value?.pinned ? "已取消置顶" : "主题已置顶"),
      onError: () => setToolbarStatus("置顶状态更新失败，请确认权限"),
    },
  );
}

function setTopicNotificationLevel(level: NotificationLevel) {
  if (!topic.value?.id) {
    return;
  }

  if (!hasAccessToken()) {
    setToolbarStatus("请先登录后再设置主题通知。");
    void router.push({ name: "auth", query: { redirect: route.fullPath } });
    return;
  }

  updateTopicNotificationMutation.mutate(level, {
    onSuccess: (response) => {
      setToolbarStatus(`主题通知已设为${notificationLevelLabel(response.notification_level)}`);
    },
    onError: () => setToolbarStatus("主题通知设置失败，请稍后重试"),
  });
}

function toggleQaSort() {
  postSort.value = postSort.value === "qa" ? "chronological" : "qa";
  setToolbarStatus(postSort.value === "qa" ? "已切换为问答排序" : "已按发布时间排序");
}

function togglePostSolution(post: PostItemVM) {
  if (!topic.value?.id || !canManageSolution.value) {
    return;
  }

  const clearing = topic.value.acceptedAnswerPostId === post.id;
  solutionMutation.mutate(
    { post_id: clearing ? null : post.id },
    {
      onSuccess: () => {
        setToolbarStatus(clearing ? "已取消采纳答案" : `已采纳 #${post.floor} 为解决方案`);
      },
      onError: () => setToolbarStatus("采纳失败，请确认主题权限和楼层状态"),
    },
  );
}

function votePoll(optionIds: string[]) {
  if (!topic.value?.poll) {
    return;
  }

  if (!hasAccessToken()) {
    setToolbarStatus("请先登录后再参与投票，当前选择已保留。");
    void router.push({ name: "auth", query: { redirect: route.fullPath } });
    return;
  }

  pollVoteMutation.mutate(
    { option_ids: optionIds },
    {
      onSuccess: () => setToolbarStatus("Poll 投票已更新"),
      onError: () => setToolbarStatus("Poll 投票失败，可能已截止或选项无效"),
    },
  );
}

function notificationLevelLabel(level: NotificationLevel): string {
  return level === "muted" ? "静音" : "关注";
}

function moveTopic() {
  const boardSlug = window.prompt("输入目标版块 slug，用于把主题更换到另一个版块：");
  const normalized = boardSlug?.trim();
  if (!normalized) {
    return;
  }

  moveTopicMutation.mutate(
    { board_slug: normalized, note: "从主题页工具栏更换主题版块" },
    {
      onSuccess: (movedTopic) => {
        setToolbarStatus(`主题已移动到 ${movedTopic.board_name}`);
        void router.replace(topicDetailRoute(movedTopic));
      },
      onError: () => setToolbarStatus("移动失败，请确认目标版块和权限"),
    },
  );
}

function deleteTopic() {
  if (!topic.value?.id || !canManageTopic.value || deleteTopicPending.value) {
    return;
  }

  const deletedTopicId = topic.value.id;
  const confirmed = window.confirm("确定删除这个主题吗？删除后主题会被软隐藏，可在审核后台恢复。");
  if (!confirmed) {
    return;
  }

  topicModerationMutation.mutate(
    {
      targetType: "topic",
      targetId: deletedTopicId,
      hidden: true,
      note: "从主题详情页删除主题",
    },
    {
      onSuccess: async () => {
        queryClient.removeQueries({ queryKey: queryKeys.topic(deletedTopicId), exact: true });
        queryClient.removeQueries({ queryKey: queryKeys.posts(deletedTopicId) });
        void queryClient.invalidateQueries({ queryKey: queryKeys.boards });
        void queryClient.invalidateQueries({ queryKey: queryKeys.topicsRoot });
        void queryClient.invalidateQueries({ queryKey: queryKeys.tagsRoot });
        await router.replace({ name: "home" });
        message.success("主题已删除，已返回首页并刷新列表。");
        void queryClient.refetchQueries({ queryKey: queryKeys.topicsRoot, type: "active" });
      },
      onError: () => setToolbarStatus("删除失败，请确认管理员权限"),
    },
  );
}

async function copyTopicLink() {
  const url =
    topic.value?.shareUrl
      ? new URL(topic.value.shareUrl, window.location.origin).href
      : window.location.href.split("#")[0];
  const copied = await writeClipboard(url);

  if (!copied) {
    window.location.hash = "topic-link-copied";
  }

  setToolbarStatus(copied ? "已复制主题链接" : "无法访问剪贴板，已更新地址栏锚点");
}

function openInviteCenter() {
  if (!hasAccessToken()) {
    requireLogin("请先登录后再邀请成员。");
    return;
  }
  void router.push({ name: "my-invites" });
}

function toggleOnlyAuthor() {
  onlyAuthor.value = !onlyAuthor.value;
  setToolbarStatus(onlyAuthor.value ? "已切换为只看楼主" : "已显示全部楼层");
}

// Toggles the reply list without changing server state.
// Key parameters: none. Return value: none; side effect: expands or collapses the local reply panel.
function toggleReplies() {
  repliesExpanded.value = !repliesExpanded.value;
}

// Records the start point for topic-level horizontal swipe navigation.
// Key parameter: `event` is the user's touch start. Return value: none; side
// effect: stores coordinates unless the gesture begins on an interactive control.
function handleTopicTouchStart(event: TouchEvent) {
  if (event.touches.length !== 1 || isTopicSwipeIgnoredTarget(event.target)) {
    topicSwipeStart.value = null;
    return;
  }

  const touch = event.touches[0];
  if (!touch) {
    topicSwipeStart.value = null;
    return;
  }
  topicSwipeStart.value = { x: touch.clientX, y: touch.clientY };
}

// Converts a clear horizontal swipe into previous/next topic navigation.
// Key parameter: `event` is the touch end. Return value: none; side effect:
// routes to the adjacent topic only when horizontal movement dominates vertical scroll.
function handleTopicTouchEnd(event: TouchEvent) {
  const start = topicSwipeStart.value;
  topicSwipeStart.value = null;
  const touch = event.changedTouches[0];
  if (!start || !touch) {
    return;
  }

  const deltaX = touch.clientX - start.x;
  const deltaY = touch.clientY - start.y;
  const absX = Math.abs(deltaX);
  const absY = Math.abs(deltaY);
  if (absX < TOPIC_HORIZONTAL_SWIPE_MIN_PX || absX < absY * TOPIC_HORIZONTAL_SWIPE_RATIO) {
    return;
  }

  navigateSwipeTopic(deltaX > 0 ? "previous" : "next");
}

// Checks whether topic swipe navigation should ignore a gesture target.
// Key parameter: `target` is the event target. Return value is true for real
// controls, editors, and custom interactive regions. Side effect: none.
function isTopicSwipeIgnoredTarget(target: EventTarget | null) {
  if (!(target instanceof Element)) {
    return false;
  }

  return Boolean(
    target.closest(
      [
        "a",
        "button",
        "input",
        "textarea",
        "select",
        "summary",
        "pre",
        "table",
        "[contenteditable='true']",
        "[role='button']",
        "[role='link']",
        ".ant-dropdown",
        ".ant-modal",
        ".ant-drawer",
        ".comic-reader",
        ".md-editor",
      ].join(","),
    ),
  );
}

// Navigates to the previous or next topic in the current board's latest feed.
// Key parameter: `direction` selects the adjacent topic. Return value: none; side effect: routes to another topic detail.
function navigateSwipeTopic(direction: "previous" | "next") {
  const target = direction === "previous" ? previousSwipeTopic.value : nextSwipeTopic.value;
  if (!target) {
    setToolbarStatus(direction === "previous" ? "已经是最新主题" : "没有更多主题");
    return;
  }

  repliesExpanded.value = false;
  replyComposerOpen.value = false;
  void router.push(topicDetailRoute(target));
}

// Checks whether a hash points into the collapsed reply area.
// Key parameter: `hash` is a route hash. Return value: true when replies must be mounted; no side effects.
function shouldExpandRepliesForHash(hash: string) {
  return hash === "#replies" || (/^#post-\d+$/.test(hash) && hash !== "#post-1");
}

// Scrolls to a hash after Vue has mounted the expanded reply list.
// Key parameter: `hash` is the element id hash. Return value: promise with no value; side effect: scrolls the page.
async function scrollHashIntoViewAfterRepliesRender(hash: string) {
  if (!hash) {
    return;
  }

  await nextTick();
  document.querySelector(hash)?.scrollIntoView({ block: "start" });
}

function quotePost(post: PostItemVM) {
  const excerpt = buildQuoteExcerpt(post);
  const quoteText = `> ${post.authorName} #${post.floor}\n> ${excerpt}\n\n`;
  openReplyComposer();
  insertReplyDraft(quoteText);
  setToolbarStatus(`已引用 ${post.authorName} #${post.floor}`);
}

function blockPostAuthor(post: PostItemVM) {
  if (post.userId === currentUserId.value) {
    setToolbarStatus("不能屏蔽自己。");
    return;
  }
  if (!hasAccessToken()) {
    requireLogin("请先登录后再屏蔽用户。");
    return;
  }
  if (blockAuthorMutation.isPending.value) {
    return;
  }
  const confirmed = window.confirm(`屏蔽 ${post.authorName}？之后将不再显示该用户的主题和楼层，也不能互发私信。`);
  if (!confirmed) {
    return;
  }
  blockAuthorMutation.mutate(post.authorName, {
    onSuccess: () => setToolbarStatus(`已屏蔽 ${post.authorName}，正在隐藏相关楼层。`),
    onError: () => setToolbarStatus("屏蔽失败，请稍后重试。"),
  });
}

function buildQuoteExcerpt(post: PostItemVM) {
  const source = post.rawMd || htmlToPlainText(post.cookedHtml);
  return source.replace(/\s+/g, " ").trim().slice(0, 180) || "（无正文）";
}

function htmlToPlainText(html: string) {
  const template = document.createElement("template");
  template.innerHTML = html;
  return template.content.textContent ?? "";
}

// Opens the mobile reply composer on demand so entering a topic does not download the editor bundle.
// Key parameters: none. Return value is none. Side effect: flips the local composer-open state.
function openReplyComposer() {
  replyComposerOpen.value = true;
}

// Sends quoted text into ComposerDrawer after it has been opened.
// Key parameter: `prefix` is Markdown to prepend. Side effect: updates insert props and focuses any mounted editor input.
function insertReplyDraft(prefix: string) {
  replyInsertText.value = prefix;
  replyInsertToken.value += 1;
}

async function writeClipboard(value: string) {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

function setToolbarStatus(message: string) {
  toolbarStatus.value = message;
  window.setTimeout(() => {
    if (toolbarStatus.value === message) {
      toolbarStatus.value = "";
    }
  }, 2600);
}

function flagTopic() {
  if (!topic.value || !canFlagTopic.value) {
    return;
  }
  reportModalOpen.value = true;
}
</script>

<template>
  <div
    class="topic-detail-page"
    :class="{ 'topic-detail-page--comic-reader': comicReader }"
    @touchstart.passive="handleTopicTouchStart"
    @touchend.passive="handleTopicTouchEnd"
  >
    <UiCard v-if="topicQuery.isLoading.value" class="topic-state" role="status">
      正在加载主题…
    </UiCard>

    <UiEmptyState
      v-else-if="topicQuery.isError.value"
      title="无法加载这个主题"
      description="这个主题暂时无法访问，可能已被删除或链接已变更。请稍后重试。"
    >
      <RouterLink class="empty-link" to="/">返回首页</RouterLink>
    </UiEmptyState>

    <template v-else-if="topic">
      <TopicDetailHero :topic="topic" :stats="topicStats" />

      <div class="topic-layout">
        <main class="post-stream" aria-label="主题正文与回复">
          <UiCard v-if="postsQuery.isLoading.value" class="topic-state" role="status">
            正在加载正文…
          </UiCard>

          <UiCard v-else-if="postsQuery.isError.value" class="topic-state topic-state--error" role="alert">
            楼层暂时加载失败，请稍后刷新。
          </UiCard>

          <template v-else>
            <div v-if="firstPost" :id="`post-${firstPost.floor}`" class="post-anchor topic-original">
              <PostItem
                :post="firstPost"
                variant="article"
                :comic-reader="comicReader"
                :current-user-id="currentUserId"
                :current-user-role="currentUserRole"
                :can-manage-solution="canManageSolution"
                :solution-pending="solutionMutation.isPending.value"
                @quote="quotePost"
                @require-login="requireLogin"
                @toggle-solution="togglePostSolution"
                @block-author="blockPostAuthor"
              />
            </div>

            <TopicThreadToolbar
              :visible-count="displayedPosts.length"
              :total-count="posts.length"
              :only-author="onlyAuthor"
              :qa-sort="qaSort"
              :bookmarked="bookmarked"
              :bookmark-count="bookmarkCount"
              :bookmark-pending="bookmarkPending"
              :topic-liked="topicLiked"
              :topic-like-count="topicLikeCount"
              :topic-like-pending="topicLikePending"
              :can-flag-topic="canFlagTopic"
              :flag-topic-pending="flagTopicPending"
              :can-manage-topic="canManageTopic"
              :topic-status="topic.status"
              :topic-pinned="Boolean(topic.pinned)"
              :lifecycle-pending="lifecyclePending"
              :delete-topic-pending="deleteTopicPending"
              :notification-level="topicNotificationLevel"
              :notification-pending="topicNotificationPending"
              :can-set-notification="canSetTopicNotification"
              :status="toolbarStatus"
              @toggle-only-author="toggleOnlyAuthor"
              @toggle-qa-sort="toggleQaSort"
              @toggle-bookmark="toggleBookmark"
              @toggle-topic-like="toggleTopicLike"
              @copy-link="copyTopicLink"
              @open-invites="openInviteCenter"
              @flag-topic="flagTopic"
              @set-notification-level="setTopicNotificationLevel"
              @set-topic-status="setTopicStatus"
              @toggle-topic-pinned="toggleTopicPinned"
              @move-topic="moveTopic"
              @delete-topic="deleteTopic"
            />

            <TopicSwipeNavigator
              :previous-topic="previousSwipeTopic"
              :next-topic="nextSwipeTopic"
              :loading="boardSwipeTopicsQuery.isFetching.value"
              @navigate="navigateSwipeTopic"
            />

            <UiCard v-if="hiddenRelationshipPostCount > 0" class="topic-state topic-state--muted" role="status">
              已隐藏 {{ hiddenRelationshipPostCount }} 条来自已屏蔽用户的楼层。
            </UiCard>

            <PollPanel
              v-if="topic.poll"
              :poll="topic.poll"
              :pending="pollVoteMutation.isPending.value"
              @vote="votePoll"
            />

            <TopicRepliesPanel
              :replies="replyPosts"
              :expanded="repliesExpanded"
              :current-user-id="currentUserId"
              :current-user-role="currentUserRole"
              :can-manage-solution="canManageSolution"
              :solution-pending="solutionMutation.isPending.value"
              @toggle="toggleReplies"
              @quote="quotePost"
              @require-login="requireLogin"
              @toggle-solution="togglePostSolution"
              @block-author="blockPostAuthor"
            />
          </template>

          <template v-if="topic.status === 'open'">
            <ComposerDrawer
              v-if="shouldRenderReplyComposer"
              mode="reply"
              :topic-title="topic.title"
              :board-name="topic.boardName"
              :submitting="createPost.isPending.value"
              :reset-token="replyResetToken"
              :draft-storage-key="`parallellines:reply-draft:${topic.id}`"
              :insert-text="replyInsertText"
              :insert-token="replyInsertToken"
              @submit="handleReply"
            />
            <UiCard v-else class="reply-compose-prompt">
              <div>
                <strong>想补充一句？</strong>
                <span>点开后再加载编辑器，先把阅读速度留给正文。</span>
              </div>
              <UiButton tone="primary" @click="openReplyComposer">参与回复</UiButton>
            </UiCard>
          </template>
          <UiCard v-else class="topic-state" role="status">
            主题当前为已关闭状态，暂不接受新回复。
          </UiCard>
          <p v-if="replyStatus" class="reply-status" role="status">{{ replyStatus }}</p>
          <span id="topic-end" class="topic-end-anchor" aria-hidden="true" />
        </main>

        <TopicDetailSidebar
          v-if="isDetailSidebarVisible"
          :topic="topic"
          :posts="displayedPosts"
          :related-topics="relatedTopics"
        />
      </div>
      <ReportModal
        v-if="topic && reportModalOpen"
        :open="reportModalOpen"
        target-type="topic"
        :target-id="topic.id"
        @close="reportModalOpen = false"
        @success="setToolbarStatus('主题举报已提交')"
      />
    </template>

    <UiEmptyState v-else title="没有找到这个主题" description="主题可能已被移动、隐藏或不存在，回到首页继续浏览。">
      <RouterLink class="empty-link" to="/">返回首页</RouterLink>
    </UiEmptyState>
  </div>
</template>

<style scoped lang="scss" src="./TopicDetailPage.scss"></style>
