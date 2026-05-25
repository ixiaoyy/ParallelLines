<script setup lang="ts">
import { CheckCircleOutlined, LockOutlined, MessageOutlined } from "@ant-design/icons-vue";
import { computed, nextTick, ref } from "vue";
import { useRouter } from "vue-router";

import type { TopicCardVM } from "@/entities/topic/model";
import { setTopicBookmark, setTopicLike } from "@/features/interactions/api";
import { useOptimisticToggle } from "@/features/interactions/useOptimisticToggle";
import { hasAccessToken } from "@/shared/api/client";
import { compactNumber, relativeTime } from "@/shared/lib/format";
import { boardToneClass, tagToneClass } from "@/shared/theme/boardPalette";
import { topicDetailPath, topicDetailRoute } from "@/shared/router/topicRoutes";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";

const props = defineProps<{ topic: TopicCardVM }>();
const router = useRouter();

const topicRoute = computed(() => topicDetailRoute(props.topic));
const visiblePosterNames = computed(() => props.topic.posterNames.slice(0, 3));
const extraPosterCount = computed(() => Math.max(props.topic.posterNames.length - visiblePosterNames.value.length, 0));
const actionStatus = ref("");
const {
  active: liked,
  count: likeCount,
  pending: likePending,
  toggle: toggleLike,
} = useOptimisticToggle({
  active: () => Boolean(props.topic.likedByMe),
  count: () => props.topic.likeCount,
  enabled: hasAccessToken,
  commit: (active) => setTopicLike(props.topic.id, active),
  readActive: (response) => response.active,
  readCount: (response) => response.count,
  onDisabled: () => requireLogin("请先登录后再点赞主题。"),
  mockWhenDisabled: false,
});
const {
  active: bookmarked,
  count: bookmarkCount,
  pending: bookmarkPending,
  toggle: toggleBookmark,
} = useOptimisticToggle({
  active: () => Boolean(props.topic.bookmarkedByMe),
  count: () => props.topic.bookmarkCount,
  enabled: hasAccessToken,
  commit: (active) => setTopicBookmark(props.topic.id, active),
  readActive: (response) => response.active,
  readCount: (response) => response.count,
  onDisabled: () => requireLogin("请先登录后再收藏主题。"),
  mockWhenDisabled: false,
});

const answerState = computed(() => {
  if (props.topic.status === "closed") {
    return { tone: "closed", label: "已关闭", helper: "只读归档" };
  }

  if (props.topic.solved) {
    return { tone: "solved", label: "已解决", helper: "优先参考" };
  }

  if (props.topic.officialReply) {
    return { tone: "official", label: "官方回复", helper: "团队已介入" };
  }

  if (props.topic.replyCount === 0) {
    return { tone: "unanswered", label: "未回复", helper: "等待首答" };
  }

  if (props.topic.featured) {
    return { tone: "featured", label: "精华", helper: "高信号" };
  }

  return { tone: "open", label: "讨论中", helper: "继续跟进" };
});

async function copyTopicLink() {
  const fallbackUrl = topicDetailPath(props.topic);
  const url = props.topic.shareUrl
    ? new URL(props.topic.shareUrl, window.location.origin).href
    : new URL(fallbackUrl, window.location.origin).href;
  const copied = await writeClipboard(url);
  setActionStatus(copied ? "已复制主题链接" : "无法访问剪贴板，请打开详情页复制");
}

async function writeClipboard(value: string) {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

function requireLogin(message: string) {
  setActionStatus(message);
  void router.push({ name: "auth", query: { redirect: topicDetailPath(props.topic) } });
}

function setActionStatus(message: string) {
  actionStatus.value = message;
  void nextTick(() => {
    window.setTimeout(() => {
      if (actionStatus.value === message) {
        actionStatus.value = "";
      }
    }, 2200);
  });
}
</script>

<template>
  <article class="topic-row" :class="[boardToneClass(topic.boardSlug), { 'topic-row--pinned': topic.pinned }]">
    <div class="topic-main">
      <div class="topic-title-line">
        <UiBadge v-if="topic.pinned" tone="amber">置顶</UiBadge>
        <UiBadge v-if="topic.featured && !topic.solved" tone="green">精华</UiBadge>
        <UiBadge v-if="topic.unreadCount" tone="blue">{{ topic.unreadCount }} 新</UiBadge>
        <LockOutlined v-if="topic.status === 'closed'" class="topic-status-icon" aria-label="已关闭" />
        <RouterLink class="topic-title" :to="topicRoute">{{ topic.title }}</RouterLink>
      </div>

      <p class="topic-excerpt">{{ topic.excerpt }}</p>

      <div class="topic-meta-line">
        <span class="category-chip tone-chip" :class="boardToneClass(topic.boardSlug)">
          <span class="category-dot tone-mark-dot" aria-hidden="true"></span>
          {{ topic.boardName }}
        </span>

        <span v-for="tag in topic.tags" :key="tag" class="topic-tag tone-chip" :class="tagToneClass(tag)">#{{ tag }}</span>
      </div>

      <div class="participant-strip" aria-label="参与者">
        <div class="participant-avatars">
          <UiAvatar
            v-for="poster in visiblePosterNames"
            :key="poster"
            :name="poster"
            size="sm"
            :title="poster"
          />
          <span v-if="extraPosterCount" class="posters-more">+{{ extraPosterCount }}</span>
        </div>
        <span>
          {{ topic.authorName }}
          <em class="author-level">Lv.{{ topic.authorLevel }}</em>
          <em class="author-trust">TL{{ topic.authorTrustLevel }} · {{ topic.authorTrustLevelLabel }}</em>
          发起 · {{ relativeTime(topic.lastPostedAt) }}有新动静
        </span>
      </div>
    </div>

    <div class="answer-state" :class="`answer-state--${answerState.tone}`">
      <CheckCircleOutlined v-if="answerState.tone === 'solved'" />
      <LockOutlined v-else-if="answerState.tone === 'closed'" />
      <strong>{{ answerState.label }}</strong>
      <small>{{ answerState.helper }}</small>
    </div>

    <div class="topic-stat">
      <div class="topic-stat__bubble">
        <MessageOutlined class="stat-icon" />
        <strong>{{ compactNumber(topic.replyCount) }}</strong>
      </div>
      <span>回复</span>
    </div>

    <div class="topic-actions" aria-label="主题互动">
      <UiButton
        :tone="liked ? 'success' : 'ghost'"
        :aria-pressed="liked"
        :disabled="likePending"
        @click="toggleLike"
      >
        {{ liked ? "已赞" : "赞" }} {{ compactNumber(likeCount) }}
      </UiButton>
      <UiButton
        :tone="bookmarked ? 'success' : 'ghost'"
        :aria-pressed="bookmarked"
        :disabled="bookmarkPending"
        @click="toggleBookmark"
      >
        {{ bookmarked ? "已藏" : "收藏" }} {{ bookmarkCount ? compactNumber(bookmarkCount) : "" }}
      </UiButton>
      <UiButton tone="subtle" @click="copyTopicLink">分享</UiButton>
      <small v-if="actionStatus" role="status">{{ actionStatus }}</small>
    </div>

    <div class="topic-activity">
      <strong>{{ relativeTime(topic.lastPostedAt) }}</strong>
      <span>{{ topic.authorName }}</span>
    </div>
  </article>
</template>

<style scoped lang="scss" src="./TopicCard.scss"></style>
