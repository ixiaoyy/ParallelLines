<script setup lang="ts">
import { useMutation, useQueryClient } from "@tanstack/vue-query";
import { message, Modal } from "ant-design-vue";
import { computed, defineAsyncComponent, nextTick, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import type { PostItemVM } from "@/entities/post/model";
import { publicSettingString } from "@/features/admin/model";
import { usePublicSiteSettings } from "@/features/admin/queries";
import { useCurrentUser } from "@/features/auth/queries";
import type { PostSort } from "@/features/posts/api";
import PostItem from "@/features/posts/components/PostItem.vue";
import { useCreatePost, useTopicPosts } from "@/features/posts/queries";
import { setUserRelationship } from "@/features/social/api";
import TopicRepliesPanel from "@/features/topics/components/TopicRepliesPanel.vue";
import TopicDetailHero from "@/features/topics/components/TopicDetailHero.vue";
import TopicSwipeNavigator from "@/features/topics/components/TopicSwipeNavigator.vue";
import {
  useBoardTopics,
  useSetTopicSolution,
  useTopicDetail,
  useVotePoll,
} from "@/features/topics/queries";
import { hasAccessToken } from "@/shared/api/client";
import { contentPolicyMessage } from "@/shared/api/errors";
import { queryKeys } from "@/shared/api/queryKeys";
import { useMediaQuery } from "@/shared/lib/useMediaQuery";
import { readRouteParam } from "@/shared/router/params";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import { useSeoMeta } from "@/shared/seo/meta";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";
import UiEmptyState from "@/shared/ui/EmptyState.vue";

const COMIC_READER_TAG = "漫画阅读";
const TOPIC_SWIPE_TOPIC_LIMIT = 24;

// Loads the reply composer only when the desktop bottom composer is visible or a mobile user opens it.
// Key parameters: none. Return value is the ComposerDrawer component; side effect is deferred editor-shell loading.
const ComposerDrawer = defineAsyncComponent(() => import("@/features/topics/components/ComposerDrawer.vue"));

// Loads poll UI only for topics that actually contain a poll.
// Key parameters: none. Return value is the PollPanel component; side effect is deferred poll chunk loading.
const PollPanel = defineAsyncComponent(() => import("@/features/topics/components/PollPanel.vue"));


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
const topic = computed(() => topicQuery.data.value);
const siteTitle = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "site_title", "平行线"),
);
const isDesktopReplyComposer = useMediaQuery("(min-width: 721px)", true);
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
const replyStatus = ref("");
const replyResetToken = ref(0);
const replyComposerOpen = ref(false);
const replyInsertText = ref("");
const replyInsertToken = ref(0);
const currentUserId = computed(() => currentUserQuery.data.value?.id ?? null);
const currentUserRole = computed(() => currentUserQuery.data.value?.role ?? null);
const comicReader = computed(() => topic.value?.tags.includes(COMIC_READER_TAG) ?? false);
const canManageTopic = computed(
  () => currentUserRole.value === "admin" || currentUserRole.value === "moderator",
);
const canManageSolution = computed(
  () => Boolean(topic.value && currentUserId.value && currentUserId.value === topic.value.authorId) || canManageTopic.value,
);
const displayedPosts = computed(() => posts.value);
const firstPost = computed(() => displayedPosts.value.find((post) => post.floor === 1) ?? displayedPosts.value[0] ?? null);
const replyPosts = computed(() => displayedPosts.value.filter((post) => post.id !== firstPost.value?.id));
const hiddenRelationshipPostCount = computed(() => {
  const expectedPostCount = (topic.value?.replyCount ?? 0) + (topic.value ? 1 : 0);
  return Math.max(0, expectedPostCount - posts.value.length);
});
const canReply = computed(() => Boolean(currentUserId.value));
const isReplyAuthChecking = computed(() => hasAccessToken() && currentUserQuery.isLoading.value);
const shouldRenderReplyComposer = computed(() =>
  topic.value?.status === "open" && canReply.value && (isDesktopReplyComposer.value || replyComposerOpen.value),
);
const boardSwipeTopicsQuery = useBoardTopics(
  () => topic.value?.boardSlug ?? "",
  "latest",
  TOPIC_SWIPE_TOPIC_LIMIT,
);
const boardSwipeTopics = computed(() => boardSwipeTopicsQuery.data.value ?? []);
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
    if (isReplyHashTarget(hash)) {
      void scrollHashIntoViewAfterRepliesRender(hash);
    }
  },
  { immediate: true },
);

function handleReply(rawMd: string) {
  replyStatus.value = "";
  if (topic.value?.status !== "open") {
    replyStatus.value = "主题当前不可回复，草稿已保留。";
    return;
  }
  if (!currentUserId.value) {
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

// Navigates to the previous or next topic in the current board's latest feed.
// Key parameter: `direction` selects the adjacent topic. Return value: none; side effect: routes to another topic detail.
function navigateSwipeTopic(direction: "previous" | "next") {
  const target = direction === "previous" ? previousSwipeTopic.value : nextSwipeTopic.value;
  if (!target) {
    setToolbarStatus(direction === "previous" ? "已经是最新主题" : "没有更多主题");
    return;
  }

  replyComposerOpen.value = false;
  void router.push(topicDetailRoute(target));
}

// Checks whether a hash points into the always-visible reply area.
// Key parameter: `hash` is a route hash. Return value: true when the page should scroll to replies; no side effects.
function isReplyHashTarget(hash: string) {
  return hash === "#replies" || (/^#post-\d+$/.test(hash) && hash !== "#post-1");
}

// Scrolls to a hash after Vue has mounted the reply list.
// Key parameter: `hash` is the element id hash. Return value: promise with no value; side effect: scrolls the page.
async function scrollHashIntoViewAfterRepliesRender(hash: string) {
  if (!hash) {
    return;
  }

  await nextTick();
  document.querySelector(hash)?.scrollIntoView({ block: "start" });
}

function quotePost(post: PostItemVM) {
  if (!canReply.value) {
    openReplyComposer();
    return;
  }

  const excerpt = buildQuoteExcerpt(post);
  const quoteText = `> ${post.authorName} #${post.floor}\n> ${excerpt}\n\n`;
  insertReplyDraft(quoteText);
  openReplyComposer();
  setToolbarStatus(`已引用 ${post.authorName} #${post.floor}`);
}

// Opens the reply composer without injecting quoted text.
// Key parameter: `post` is the floor that initiated the action. Side effect: reveals and scrolls to the composer.
function replyToPost(post: PostItemVM) {
  clearReplyInsertRequest();
  openReplyComposer();
  if (canReply.value) {
    setToolbarStatus(`正在回复 ${post.authorName} #${post.floor}`);
  }
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
  Modal.confirm({
    title: `屏蔽 ${post.authorName}？`,
    content: "之后将不再显示该用户的主题和楼层，也不能互发私信。",
    okText: "屏蔽用户",
    cancelText: "取消",
    okType: "danger",
    onOk: () => {
      blockAuthorMutation.mutate(post.authorName, {
        onSuccess: () => setToolbarStatus(`已屏蔽 ${post.authorName}，正在隐藏相关楼层。`),
        onError: () => setToolbarStatus("屏蔽失败，请稍后重试。"),
      });
    },
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
  if (!canReply.value) {
    replyStatus.value = "登录后才能发布回复，当前页面会在登录后继续打开。";
    void router.push({ name: "auth", query: { redirect: route.fullPath } });
    return;
  }

  replyComposerOpen.value = true;
  void scrollReplyComposerIntoView();
}

// Queues quoted text for ComposerDrawer before or after the editor is mounted.
// Key parameter: `prefix` is Markdown to prepend. Side effect: updates insert props and focuses any mounted editor input.
function insertReplyDraft(prefix: string) {
  replyInsertText.value = prefix;
  replyInsertToken.value += 1;
}

// Clears any queued quote text before a plain reply opens the composer.
// Key parameters: none. Return value: none. Side effect: prevents stale quote props on the next mount.
function clearReplyInsertRequest() {
  replyInsertText.value = "";
}

// Scrolls the revealed reply composer into view and focuses its editable area when mounted.
// Key parameters: none. Return value: promise with no value. Side effect: scrolls and focuses browser UI.
async function scrollReplyComposerIntoView() {
  await nextTick();
  const composer = document.getElementById("reply-composer");
  composer?.scrollIntoView({ block: "start", behavior: "smooth" });
  const focusTarget = composer?.querySelector<HTMLElement>(
    ".cm-content, textarea, [contenteditable='true']",
  );
  window.setTimeout(() => {
    focusTarget?.focus();
  }, 180);
}

function setToolbarStatus(content: string) {
  void message.open({ key: "topic-detail-status", type: "info", content, duration: 2.6 });
}

</script>

<template>
  <div class="topic-detail-page" :class="{ 'topic-detail-page--comic-reader': comicReader }">
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
      <TopicDetailHero :topic="topic" />

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
                hide-header
                :current-user-id="currentUserId"
                :current-user-role="currentUserRole"
                :can-manage-solution="canManageSolution"
                :solution-pending="solutionMutation.isPending.value"
                @quote="quotePost"
                @reply="replyToPost"
                @require-login="requireLogin"
                @toggle-solution="togglePostSolution"
                @block-author="blockPostAuthor"
              />
            </div>
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
              :current-user-id="currentUserId"
              :current-user-role="currentUserRole"
              :can-manage-solution="canManageSolution"
              :solution-pending="solutionMutation.isPending.value"
              @quote="quotePost"
              @reply="replyToPost"
              @require-login="requireLogin"
              @toggle-solution="togglePostSolution"
              @block-author="blockPostAuthor"
            />
          </template>

          <template v-if="topic.status === 'open'">
            <div v-if="shouldRenderReplyComposer" id="reply-composer" class="reply-composer-anchor">
              <ComposerDrawer
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
            </div>
            <UiCard v-else class="reply-compose-prompt">
              <div>
                <strong>{{ canReply ? "想补充一句？" : isReplyAuthChecking ? "正在确认登录状态" : "登录后参与回复" }}</strong>
                <span>{{ canReply ? "点开后再加载编辑器，先把阅读速度留给正文。" : "登录后才能打开编辑器；回来后可以继续阅读这个主题。" }}</span>
              </div>
              <UiButton tone="primary" :disabled="isReplyAuthChecking" @click="openReplyComposer">
                {{ canReply ? "参与回复" : "登录/注册" }}
              </UiButton>
            </UiCard>
          </template>
          <UiCard v-else class="topic-state" role="status">
            主题当前为已关闭状态，暂不接受新回复。
          </UiCard>
          <p v-if="replyStatus" class="reply-status" role="status">{{ replyStatus }}</p>
          <span id="topic-end" class="topic-end-anchor" aria-hidden="true" />
        </main>
      </div>

    </template>

    <UiEmptyState v-else title="没有找到这个主题" description="主题可能已被移动、隐藏或不存在，回到首页继续浏览。">
      <RouterLink class="empty-link" to="/">返回首页</RouterLink>
    </UiEmptyState>
  </div>
</template>

<style scoped lang="scss" src="./TopicDetailPage.scss"></style>
