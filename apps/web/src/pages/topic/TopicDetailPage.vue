<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import type { PostItemVM } from "@/entities/post/model";
import { useCurrentUser } from "@/features/auth/queries";
import { setTopicBookmark } from "@/features/interactions/api";
import { useOptimisticToggle } from "@/features/interactions/useOptimisticToggle";
import { useCreateFlag } from "@/features/moderation/queries";
import PostItem from "@/features/posts/components/PostItem.vue";
import { useCreatePost, useTopicPosts } from "@/features/posts/queries";
import ComposerDrawer from "@/features/topics/components/ComposerDrawer.vue";
import TopicDetailHero from "@/features/topics/components/TopicDetailHero.vue";
import TopicDetailSidebar from "@/features/topics/components/TopicDetailSidebar.vue";
import TopicThreadToolbar from "@/features/topics/components/TopicThreadToolbar.vue";
import {
  useMergeTopic,
  useMoveTopic,
  useRelatedTopics,
  useSplitTopic,
  useTopicDetail,
  useTopicLifecycle,
} from "@/features/topics/queries";
import { hasAccessToken } from "@/shared/api/client";
import { contentPolicyMessage } from "@/shared/api/errors";
import { compactNumber } from "@/shared/lib/format";
import { readRouteParam } from "@/shared/router/params";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import UiCard from "@/shared/ui/Card.vue";
import UiEmptyState from "@/shared/ui/EmptyState.vue";

const route = useRoute();
const router = useRouter();

const topicId = computed(() => readRouteParam(route.params.id));
const topicQuery = useTopicDetail(topicId);
const postsQuery = useTopicPosts(topicId);
const createPost = useCreatePost(topicId);
const currentUserQuery = useCurrentUser();
const topic = computed(() => topicQuery.data.value);
const posts = computed(() => postsQuery.data.value ?? []);
const onlyAuthor = ref(false);
const toolbarStatus = ref("");
const replyStatus = ref("");
const replyResetToken = ref(0);
const currentUserId = computed(() => currentUserQuery.data.value?.id ?? null);
const currentUserRole = computed(() => currentUserQuery.data.value?.role ?? null);
const canManageTopic = computed(
  () => currentUserRole.value === "admin" || currentUserRole.value === "moderator",
);
const displayedPosts = computed(() => {
  if (!onlyAuthor.value || !topic.value) {
    return posts.value;
  }

  return posts.value.filter((post) => post.authorName === topic.value?.authorName);
});
const relatedTopics = useRelatedTopics(topic);
const flagTopicMutation = useCreateFlag();
const lifecycleMutation = useTopicLifecycle(topicId);
const moveTopicMutation = useMoveTopic(topicId);
const splitTopicMutation = useSplitTopic(topicId);
const mergeTopicMutation = useMergeTopic(topicId);
const canFlagTopic = computed(() => Boolean(topic.value?.id) && hasAccessToken());
const flagTopicPending = computed(() => flagTopicMutation.isPending.value);
const lifecyclePending = computed(
  () =>
    lifecycleMutation.isPending.value ||
    moveTopicMutation.isPending.value ||
    splitTopicMutation.isPending.value ||
    mergeTopicMutation.isPending.value,
);
const {
  active: bookmarked,
  count: bookmarkCount,
  pending: bookmarkPending,
  toggle: toggleBookmark,
} = useOptimisticToggle({
  active: () => Boolean(topic.value?.id) && false,
  count: () => (topic.value ? 0 : 0),
  enabled: hasAccessToken,
  commit: (active) => setTopicBookmark(topic.value?.id ?? "", active),
  readActive: (response) => response.active,
  readCount: (response) => response.count,
});

const topicStats = computed(() => {
  if (!topic.value) {
    return [];
  }

  return [
    { label: "回复", value: compactNumber(topic.value.replyCount) },
    { label: "浏览", value: compactNumber(topic.value.viewCount) },
    { label: "赞同", value: compactNumber(topic.value.likeCount) },
    { label: "热度", value: String(topic.value.hotScore) },
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

function setTopicStatus(status: "open" | "closed" | "archived") {
  lifecycleMutation.mutate(
    { status, note: "从主题页工具栏更新状态" },
    {
      onSuccess: () => setToolbarStatus(status === "open" ? "主题已重新打开" : "主题状态已更新"),
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

function moveTopic() {
  const boardSlug = window.prompt("输入目标版块 slug：");
  const normalized = boardSlug?.trim();
  if (!normalized) {
    return;
  }

  moveTopicMutation.mutate(
    { board_slug: normalized, note: "从主题页工具栏移动主题" },
    {
      onSuccess: (movedTopic) => {
        setToolbarStatus(`主题已移动到 ${movedTopic.board_name}`);
        void router.replace(topicDetailRoute(movedTopic));
      },
      onError: () => setToolbarStatus("移动失败，请确认目标版块和权限"),
    },
  );
}

function splitTopic() {
  const floors = window.prompt("输入要拆分的楼层号，多个用英文逗号分隔（不能包含 1 楼）：");
  const floorNumbers = parseFloorNumbers(floors ?? "");
  if (!floorNumbers.length) {
    return;
  }
  const selectedPosts = posts.value.filter((post) => floorNumbers.includes(post.floor));
  if (selectedPosts.length !== floorNumbers.length || selectedPosts.some((post) => post.floor === 1)) {
    setToolbarStatus("拆分楼层无效，请确认楼层存在且不包含 1 楼");
    return;
  }
  const title = window.prompt("输入新主题标题：", `${topic.value?.title ?? "新主题"}（拆分）`);
  const normalizedTitle = title?.trim();
  if (!normalizedTitle) {
    return;
  }

  splitTopicMutation.mutate(
    {
      title: normalizedTitle,
      post_ids: selectedPosts.map((post) => post.id),
      note: "从主题页工具栏拆分回复",
    },
    {
      onSuccess: (response) => {
        setToolbarStatus(`已拆分 ${response.moved_post_count} 个楼层为新主题`);
      },
      onError: () => setToolbarStatus("拆分失败，请确认楼层和权限"),
    },
  );
}

function mergeTopic() {
  const targetTopicId = window.prompt("输入要合并到的目标主题 ID：");
  const normalized = targetTopicId?.trim();
  if (!normalized || normalized === topic.value?.id) {
    return;
  }

  mergeTopicMutation.mutate(
    { target_topic_id: normalized, note: "从主题页工具栏合并主题" },
    {
      onSuccess: (response) => {
        setToolbarStatus(`已合并 ${response.moved_post_count} 个楼层`);
        void router.replace(topicDetailRoute(response.target_topic));
      },
      onError: () => setToolbarStatus("合并失败，请确认目标主题和权限"),
    },
  );
}

function parseFloorNumbers(value: string) {
  return [
    ...new Set(
      value
        .split(",")
        .map((item) => Number.parseInt(item.trim(), 10))
        .filter((item) => Number.isInteger(item) && item > 0),
    ),
  ];
}

async function copyTopicLink() {
  const url = window.location.href.split("#")[0];
  const copied = await writeClipboard(url);

  if (!copied) {
    window.location.hash = "topic-link-copied";
  }

  setToolbarStatus(copied ? "已复制主题链接" : "无法访问剪贴板，已更新地址栏锚点");
}

function toggleOnlyAuthor() {
  onlyAuthor.value = !onlyAuthor.value;
  setToolbarStatus(onlyAuthor.value ? "已切换为只看楼主" : "已显示全部楼层");
}

function quotePost(post: PostItemVM) {
  const excerpt = buildQuoteExcerpt(post);
  const quoteText = `> ${post.authorName} #${post.floor}\n> ${excerpt}\n\n`;
  injectReplyDraft(quoteText);
  setToolbarStatus(`已引用 ${post.authorName} #${post.floor}`);
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

function injectReplyDraft(prefix: string) {
  void nextTick(() => {
    const textarea = document.querySelector<HTMLTextAreaElement>('textarea[aria-label="回复正文"]');
    if (!textarea) {
      return;
    }

    textarea.focus();
    textarea.value = `${prefix}${textarea.value}`;
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  });
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

  flagTopicMutation.mutate({
    target_type: "topic",
    target_id: topic.value.id,
    reason: "other",
    detail: "用户从主题工具栏发起举报。",
  });
}
</script>

<template>
  <div class="topic-detail-page">
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
        <main class="post-stream" aria-label="楼层流">
          <TopicThreadToolbar
            :visible-count="displayedPosts.length"
            :total-count="posts.length"
            :only-author="onlyAuthor"
            :bookmarked="bookmarked"
            :bookmark-count="bookmarkCount"
            :bookmark-pending="bookmarkPending"
            :can-flag-topic="canFlagTopic"
            :flag-topic-pending="flagTopicPending"
            :can-manage-topic="canManageTopic"
            :topic-status="topic.status"
            :topic-pinned="Boolean(topic.pinned)"
            :lifecycle-pending="lifecyclePending"
            :status="toolbarStatus"
            @toggle-only-author="toggleOnlyAuthor"
            @toggle-bookmark="toggleBookmark"
            @copy-link="copyTopicLink"
            @flag-topic="flagTopic"
            @set-topic-status="setTopicStatus"
            @toggle-topic-pinned="toggleTopicPinned"
            @move-topic="moveTopic"
            @split-topic="splitTopic"
            @merge-topic="mergeTopic"
          />

          <div class="post-list">
            <UiCard v-if="postsQuery.isError.value" class="topic-state topic-state--error" role="alert">
              楼层暂时加载失败，请稍后刷新。
            </UiCard>
            <div v-for="post in displayedPosts" :id="`post-${post.floor}`" :key="post.id" class="post-anchor">
              <PostItem
                :post="post"
                :current-user-id="currentUserId"
                :current-user-role="currentUserRole"
                @quote="quotePost"
              />
            </div>
          </div>

          <ComposerDrawer
            v-if="topic.status === 'open'"
            mode="reply"
            :topic-title="topic.title"
            :board-name="topic.boardName"
            :submitting="createPost.isPending.value"
            :reset-token="replyResetToken"
            :draft-storage-key="`parallellines:reply-draft:${topic.id}`"
            @submit="handleReply"
          />
          <UiCard v-else class="topic-state" role="status">
            主题当前为 {{ topic.status === "closed" ? "已关闭" : "已归档" }} 状态，暂不接受新回复。
          </UiCard>
          <p v-if="replyStatus" class="reply-status" role="status">{{ replyStatus }}</p>
        </main>

        <TopicDetailSidebar :topic="topic" :posts="displayedPosts" :related-topics="relatedTopics" />
      </div>
    </template>

    <UiEmptyState v-else title="没有找到这个主题" description="主题可能已被合并或隐藏，回到首页继续浏览。">
      <RouterLink class="empty-link" to="/">返回首页</RouterLink>
    </UiEmptyState>
  </div>
</template>

<style scoped lang="scss" src="./TopicDetailPage.scss"></style>
