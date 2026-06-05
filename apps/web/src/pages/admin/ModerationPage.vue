<script setup lang="ts">
import { computed, ref } from "vue";
import {
  EyeOutlined,
  FlagOutlined,
  HistoryOutlined,
} from "@ant-design/icons-vue";

import { isAdmin } from "@/features/auth/permissions";
import { useCurrentUser } from "@/features/auth/queries";
import {
  auditActionLabel,
  flagReasonLabel,
  flagStatusLabel,
  reviewableStatusLabel,
  reviewableTypeLabel,
} from "@/features/moderation/model";
import type {
  FlagResponse,
  FlagStatus,
  UserModerationStatus,
  ReviewableResponse,
  ReviewableStatus,
  ReviewableDecisionAction,
} from "@/features/moderation/model";
import {
  useAuditLogs,
  useContentModerationMutation,
  useFlagStatusMutation,
  useModerationQueue,
  useUserStatusMutation,
  usePublishReviewableQueue,
  useReviewableDecisionMutation,
} from "@/features/moderation/queries";
import { hasAccessToken } from "@/shared/api/client";
import { relativeTime } from "@/shared/lib/format";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

interface FrontierPreviewCard {
  source: string;
  imageAlt: string;
  imageUrl: string;
  title: string;
  url: string;
  summary: string;
}

const activeTab = ref<"reviewables" | "flags" | "audit">("reviewables");
const reviewablesTabActive = computed(() => activeTab.value === "reviewables");
const flagsTabActive = computed(() => activeTab.value === "flags");
const auditTabActive = computed(() => activeTab.value === "audit");

// Flag filter & query
const statusFilter = ref<FlagStatus | "all">("pending");
const selectedQueueStatus = computed<FlagStatus | undefined>(() =>
  statusFilter.value === "all" ? undefined : statusFilter.value,
);
const queueQuery = useModerationQueue(selectedQueueStatus, flagsTabActive);

// Reviewable filter & query
const reviewableStatusFilter = ref<ReviewableStatus | "all">("pending");
const reviewablesQuery = usePublishReviewableQueue(reviewableStatusFilter, reviewablesTabActive);

const auditQuery = useAuditLogs(auditTabActive);
const flagStatusMutation = useFlagStatusMutation();
const contentMutation = useContentModerationMutation();
const userStatusMutation = useUserStatusMutation();
const currentUserQuery = useCurrentUser();

const decisionMutation = useReviewableDecisionMutation();

const userId = ref("");
const userStatus = ref<UserModerationStatus>("silenced");
const userNote = ref("");
const actionNotice = ref("");
const actionError = ref("");
const activeReviewableId = ref<string | null>(null);
const activeFlagId = ref<string | null>(null);
const activeContentFlagId = ref<string | null>(null);
const userStatusUpdating = ref(false);
const hasToken = computed(() => hasAccessToken());
const canUpdateUserStatus = computed(() => isAdmin(currentUserQuery.data.value));
const currentUserId = computed(() => currentUserQuery.data.value?.id);

const flags = computed(() => queueQuery.data.value ?? []);
const reviewables = computed(() => reviewablesQuery.data.value ?? []);
const auditLogs = computed(() => auditQuery.data.value ?? []);

const queueError = computed(() =>
  (flagsTabActive.value && queueQuery.isError.value) ||
  (reviewablesTabActive.value && reviewablesQuery.isError.value) ||
  (auditTabActive.value && auditQuery.isError.value),
);

const pendingAction = computed(
  () =>
    flagStatusMutation.isPending.value ||
    contentMutation.isPending.value ||
    userStatusMutation.isPending.value ||
    decisionMutation.isPending.value,
);
const activeReviewablePendingId = computed(() =>
  decisionMutation.isPending.value ? activeReviewableId.value : null,
);
const activeFlagPendingId = computed(() =>
  flagStatusMutation.isPending.value ? activeFlagId.value : null,
);
const activeContentPendingFlagId = computed(() =>
  contentMutation.isPending.value ? activeContentFlagId.value : null,
);
const activeFeedback = computed<{
  tone: "working" | "success" | "error";
  title: string;
  detail: string;
} | null>(() => {
  if (actionError.value) {
    return {
      tone: "error",
      title: "操作失败",
      detail: actionError.value,
    };
  }

  if (pendingAction.value) {
    return {
      tone: "working",
      title: "正在处理",
      detail: "接口正在响应，完成后会自动刷新审核队列。",
    };
  }

  if (
    reviewablesQuery.isFetching.value ||
    queueQuery.isFetching.value ||
    auditQuery.isFetching.value
  ) {
    return {
      tone: "working",
      title: "正在刷新",
      detail: "正在同步最新审核数据。",
    };
  }

  if (actionNotice.value) {
    return {
      tone: "success",
      title: "已完成",
      detail: actionNotice.value,
    };
  }

  return null;
});

// Drawer state
const selectedReviewable = ref<ReviewableResponse | null>(null);
const isDrawerOpen = computed(() => selectedReviewable.value !== null);
const selectedFrontierPreviewCard = computed(() =>
  selectedReviewable.value ? frontierPreviewCard(selectedReviewable.value) : null,
);
const decisionAction = ref<ReviewableDecisionAction>("approve");
const decisionNote = ref("");

function openReviewableDetails(reviewable: ReviewableResponse) {
  selectedReviewable.value = reviewable;
  decisionAction.value = "approve";
  decisionNote.value = "";
}

function closeDrawer() {
  selectedReviewable.value = null;
}

function submitDecision() {
  if (!selectedReviewable.value) return;
  decideReviewable(selectedReviewable.value, decisionAction.value, decisionNote.value, closeDrawer);
}

function hasReviewableTarget(reviewable: ReviewableResponse) {
  return Boolean(reviewable.target_id && ["topic", "post"].includes(reviewable.target_type ?? ""));
}

function canSilenceReviewable(reviewable: ReviewableResponse) {
  return Boolean(reviewable.target_user_id);
}

function canDecideReviewable(reviewable: ReviewableResponse) {
  if (!["pending", "appealed", "claimed"].includes(reviewable.status)) {
    return false;
  }

  return !isClaimedByOther(reviewable);
}

function isClaimedByOther(reviewable: ReviewableResponse) {
  return Boolean(
    reviewable.status === "claimed" &&
      reviewable.assigned_to_id &&
      reviewable.assigned_to_id !== currentUserId.value,
  );
}

function textField(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function reviewableTitle(reviewable: ReviewableResponse) {
  return textField(reviewable.data.title) || reviewable.source_summary || "待审核内容";
}

function reviewableReason(reviewable: ReviewableResponse) {
  if (reviewable.source === "frontier_news") {
    return "资讯机器人自动采集并整理；审核通过后会直接发布到前沿资讯版块。";
  }

  if (
    reviewable.source === "seed_content" ||
    reviewable.source === "persona_content" ||
    reviewable.data.seed_author === true ||
    reviewable.data.persona_seed === true
  ) {
    return "新用户发帖，发布前需要审核通过。";
  }

  if (reviewable.source === "content_safety") {
    return "命中内容安全规则，需要人工确认。";
  }

  if (String(reviewable.type).startsWith("queued_")) {
    return "内容需要审核通过后才会公开。";
  }

  return reviewable.source_summary || "需要人工审核。";
}

function reviewablePreview(reviewable: ReviewableResponse) {
  if (reviewable.source === "frontier_news") {
    const rawMarkdown = textField(reviewable.data.raw_md);
    const previewMarkdown = rawMarkdown
      .replace(/(^|\n):::\s*news-card\s*(?=\n|$)/g, "")
      .replace(/(^|\n):::\s*(?=\n|$)/g, "")
      .replace(/(^|\n)\s*一句话：.*(?=\n|$)/g, "")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
    return previewMarkdown || reviewableReason(reviewable);
  }

  return (
    textField(reviewable.data.raw_md) ||
    textField(reviewable.data.excerpt) ||
    reviewableReason(reviewable)
  );
}

/**
 * Parses the controlled frontier `news-card` Markdown block for the moderation drawer preview.
 */
function frontierPreviewCard(reviewable: ReviewableResponse): FrontierPreviewCard | null {
  if (reviewable.source !== "frontier_news") return null;
  const rawMarkdown = textField(reviewable.data.raw_md);
  if (rawMarkdown.includes(":::news-card")) {
    return parseFrontierNewsCard(rawMarkdown);
  }
  return parseLegacyFrontierNewsCard(rawMarkdown, reviewable);
}

/**
 * Extracts source, optional image, title link, and summary from generated frontier Markdown.
 */
function parseFrontierNewsCard(rawMarkdown: string): FrontierPreviewCard | null {
  const block = rawMarkdown.match(/:::news-card\s*([\s\S]*?)\n:::/);
  const lines = (block?.[1] ?? rawMarkdown)
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return null;

  const card: FrontierPreviewCard = {
    source: "",
    imageAlt: "",
    imageUrl: "",
    title: "",
    url: "",
    summary: "",
  };
  const summaryLines: string[] = [];
  for (const line of lines) {
    const image = line.match(/^!\[([^\]\n]*)]\((https?:\/\/[^)\s]+|\/[^\s)]+)\)$/);
    if (image && !card.imageUrl) {
      card.imageAlt = image[1];
      card.imageUrl = image[2];
      continue;
    }
    const link = line.match(/^\[([^\]\n]+)]\((https?:\/\/[^)\s]+|\/[^\s)]+)\)$/);
    if (link && !card.url) {
      card.title = link[1];
      card.url = link[2];
      continue;
    }
    if (!card.source) {
      card.source = line;
    } else {
      summaryLines.push(line);
    }
  }
  card.summary = summaryLines.join("\n").trim();
  return card.title && card.url && card.summary ? card : null;
}

/**
 * Converts older frontier plain-text drafts into the same card preview shape.
 */
function parseLegacyFrontierNewsCard(
  rawMarkdown: string,
  reviewable: ReviewableResponse,
): FrontierPreviewCard | null {
  const lines = rawMarkdown
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const original = lines.find((line) => line.startsWith("原文：")) ?? "";
  const source = lines.find((line) => line.startsWith("来源：")) || textField(reviewable.data.source_name);
  const summary = (
    lines.find((line) => line.startsWith("原文摘要："))?.replace(/^原文摘要：/, "") ||
    textField(reviewable.data.excerpt)
  ).trim();
  const link = original.match(/^原文：\[([^\]\n]+)]\((https?:\/\/[^)\s]+|\/[^\s)]+)\)$/);
  const title = link?.[1] || textField(reviewable.data.original_title) || reviewableTitle(reviewable);
  const url = link?.[2] || textField(reviewable.data.source_url);
  return title && url && summary
    ? {
        source,
        imageAlt: "",
        imageUrl: "",
        title,
        url,
        summary,
      }
    : null;
}

function decideReviewable(
  reviewable: ReviewableResponse,
  action: ReviewableDecisionAction,
  note: string,
  onSuccess?: () => void,
) {
  resetActionFeedback();
  activeReviewableId.value = reviewable.id;
  decisionMutation.mutate(
    {
      reviewableId: reviewable.id,
      payload: {
        action,
        note: note.trim() || null,
      },
    },
    {
      onSuccess: (updatedReviewable) => {
        selectedReviewable.value = updatedReviewable;
        actionNotice.value = `${reviewableTitle(updatedReviewable)}：${reviewableStatusLabel(
          updatedReviewable.status,
        )}`;
        onSuccess?.();
      },
      onError: (error) => {
        actionError.value = mutationErrorMessage(error);
      },
      onSettled: () => {
        activeReviewableId.value = null;
      },
    },
  );
}

function approveReviewable(reviewable: ReviewableResponse) {
  decideReviewable(reviewable, "approve", "审核通过，允许发布。");
}

function rejectReviewable(reviewable: ReviewableResponse) {
  decideReviewable(reviewable, "reject", "审核拒绝，不予发布。");
}

function resolveFlag(flag: FlagResponse) {
  resetActionFeedback();
  activeFlagId.value = flag.id;
  flagStatusMutation.mutate({
    flagId: flag.id,
    payload: { status: "resolved", resolution_note: "已由审核台处理。" },
  }, {
    onSuccess: () => {
      actionNotice.value = `${flag.target.title}：已标记处理。`;
    },
    onError: (error) => {
      actionError.value = mutationErrorMessage(error);
    },
    onSettled: () => {
      activeFlagId.value = null;
    },
  });
}

function rejectFlag(flag: FlagResponse) {
  resetActionFeedback();
  activeFlagId.value = flag.id;
  flagStatusMutation.mutate({
    flagId: flag.id,
    payload: { status: "rejected", resolution_note: "未发现违规或证据不足。" },
  }, {
    onSuccess: () => {
      actionNotice.value = `${flag.target.title}：已驳回举报。`;
    },
    onError: (error) => {
      actionError.value = mutationErrorMessage(error);
    },
    onSettled: () => {
      activeFlagId.value = null;
    },
  });
}

function toggleHidden(flag: FlagResponse) {
  resetActionFeedback();
  activeContentFlagId.value = flag.id;
  contentMutation.mutate({
    targetType: flag.target.target_type,
    targetId: flag.target.target_id,
    hidden: !flag.target.hidden,
    note: flag.target.hidden ? "审核台恢复内容。" : "审核台隐藏内容。",
  }, {
    onSuccess: (response) => {
      actionNotice.value = `${flag.target.title}：${response.hidden ? "已隐藏" : "已恢复"}。`;
    },
    onError: (error) => {
      actionError.value = mutationErrorMessage(error);
    },
    onSettled: () => {
      activeContentFlagId.value = null;
    },
  });
}

function updateUser() {
  const trimmedUserId = userId.value.trim();
  if (!trimmedUserId) {
    return;
  }

  resetActionFeedback();
  userStatusUpdating.value = true;
  userStatusMutation.mutate(
    {
      userId: trimmedUserId,
      payload: { status: userStatus.value, note: userNote.value.trim() || null },
    },
    {
      onSuccess: (response) => {
        actionNotice.value = `${response.username}：状态已更新为 ${response.status}。`;
      },
      onError: (error) => {
        actionError.value = mutationErrorMessage(error);
      },
      onSettled: () => {
        userStatusUpdating.value = false;
      },
    },
  );
}

function targetRoute(flag: FlagResponse) {
  const topicId = flag.target.topic_id ?? flag.target.target_id;
  const topicSlug = flag.target.topic_slug ?? flag.target.board_slug;
  return topicDetailRoute({
    id: topicId,
    slug: topicSlug,
    hash: flag.target.post_number ? `post-${flag.target.post_number}` : null,
  });
}

function flagDetail(flag: FlagResponse) {
  return flag.detail?.trim() || "举报人未填写补充说明。";
}

function flagTargetExcerpt(flag: FlagResponse) {
  return flag.target.excerpt?.trim() || "暂无内容摘要，请打开上下文查看原帖。";
}

/**
 * Clears stale operation messages before starting a moderation mutation.
 *
 * Side effect: removes previous success/error copy so the new pending state is unambiguous.
 */
function resetActionFeedback() {
  actionNotice.value = "";
  actionError.value = "";
}

/**
 * Converts mutation failures into short operator-facing text.
 *
 * @param error - Unknown error object returned by TanStack Query mutation callbacks.
 * @returns Human-readable error message that can be displayed in the moderation console.
 */
function mutationErrorMessage(error: unknown) {
  return error instanceof Error && error.message ? error.message : "接口请求失败，请稍后重试。";
}
</script>

<template>
  <div class="moderation-page">
    <section class="moderation-hero" aria-labelledby="moderation-title">
      <div>
        <span class="panel-kicker">审核台</span>
        <h1 id="moderation-title">内容审核</h1>
        <p>这里分两件事：审核帖子是否发布；查看用户举报原因，并处理被举报的帖子或回复。</p>
      </div>
      <RouterLink class="hero-link" to="/admin">返回后台</RouterLink>
    </section>

    <UiCard v-if="!hasToken" class="moderation-empty">
      <strong>需要登录后才能查看审核台</strong>
      <span>请使用拥有版主、版主所有者或管理员权限的账号访问。</span>
    </UiCard>

    <UiCard v-else-if="queueError" class="moderation-empty">
      <strong>没有审核权限或服务暂不可用</strong>
      <span>普通用户可以举报内容，但不能查看审核队列或审计日志。</span>
    </UiCard>

    <template v-else>
      <!-- Navigation Tabs -->
      <nav class="moderation-tabs" aria-label="审核台导航">
        <button :class="{ active: activeTab === 'reviewables' }" @click="activeTab = 'reviewables'">
          <EyeOutlined /> 帖子发布审核
        </button>
        <button :class="{ active: activeTab === 'flags' }" @click="activeTab = 'flags'">
          <FlagOutlined /> 用户举报审核
        </button>
        <button :class="{ active: activeTab === 'audit' }" @click="activeTab = 'audit'">
          <HistoryOutlined /> 日志
        </button>
      </nav>

      <div
        v-if="activeFeedback"
        class="moderation-feedback"
        :class="`moderation-feedback--${activeFeedback.tone}`"
        :role="activeFeedback.tone === 'error' ? 'alert' : 'status'"
        aria-live="polite"
      >
        <span v-if="activeFeedback.tone === 'working'" class="moderation-feedback__spinner" aria-hidden="true"></span>
        <strong>{{ activeFeedback.title }}</strong>
        <span>{{ activeFeedback.detail }}</span>
      </div>

      <section class="moderation-layout" :class="{ 'moderation-layout--single': activeTab !== 'audit' }">
        <!-- Main Column -->
        <main class="queue-column">
          <!-- Tab 1: Reviewables -->
          <div v-if="activeTab === 'reviewables'">
            <div class="section-toolbar">
              <div>
                <span class="panel-kicker">帖子发布审核</span>
                <h2>审核待发布的帖子</h2>
              </div>
              <label>
                <span>查看状态</span>
                <select v-model="reviewableStatusFilter">
                  <option value="pending">待处理</option>
                  <option value="claimed">处理中</option>
                  <option value="approved">已通过</option>
                  <option value="rejected">已拒绝</option>
                  <option value="hidden">已隐藏</option>
                  <option value="deleted">已删除</option>
                  <option value="silenced">已禁言</option>
                  <option value="escalated">已升级</option>
                  <option value="appealed">复核中</option>
                  <option value="all">全部</option>
                </select>
              </label>
            </div>

            <UiCard v-if="reviewablesQuery.isPending.value" class="moderation-empty moderation-empty--loading">
              <strong>正在加载审核队列</strong>
              <span>请稍候，待发布内容加载完成后会显示在这里。</span>
            </UiCard>

            <div v-else-if="reviewables.length" class="flag-list">
              <article v-for="rev in reviewables" :key="rev.id" class="flag-card reviewable-card">
                <header>
                  <div>
                    <span class="flag-meta">
                      {{ reviewableTypeLabel(rev.type) }} · {{ reviewableStatusLabel(rev.status) }} ·
                      {{ relativeTime(rev.created_at) }}
                    </span>
                    <h3>{{ reviewableTitle(rev) }}</h3>
                  </div>
                  <button class="detail-link-btn" @click="openReviewableDetails(rev)">
                    查看全文
                  </button>
                </header>

                <p class="reviewable-reason">{{ reviewableReason(rev) }}</p>
                <p class="reviewable-excerpt">{{ reviewablePreview(rev) }}</p>

                <dl>
                  <div>
                    <dt>类型</dt>
                    <dd>{{ reviewableTypeLabel(rev.type) }}</dd>
                  </div>
                  <div>
                    <dt>作者</dt>
                    <dd>{{ rev.target_user_name || rev.created_by_name || '系统' }}</dd>
                  </div>
                  <div>
                    <dt>版块</dt>
                    <dd>{{ rev.board_name || '全局' }}</dd>
                  </div>
                  <div>
                    <dt>状态</dt>
                    <dd>{{ reviewableStatusLabel(rev.status) }}</dd>
                  </div>
                </dl>

                <footer>
                  <div class="footer-actions">
                    <template v-if="canDecideReviewable(rev)">
                      <UiButton tone="success" :disabled="pendingAction" @click="approveReviewable(rev)">
                        {{ activeReviewablePendingId === rev.id ? "处理中…" : "通过发布" }}
                      </UiButton>
                      <UiButton tone="ghost" :disabled="pendingAction" @click="rejectReviewable(rev)">
                        {{ activeReviewablePendingId === rev.id ? "处理中…" : "拒绝" }}
                      </UiButton>
                      <UiButton tone="subtle" :disabled="pendingAction" @click="openReviewableDetails(rev)">
                        {{ activeReviewablePendingId === rev.id ? "处理中…" : "更多处理" }}
                      </UiButton>
                    </template>
                    <template v-else-if="isClaimedByOther(rev)">
                      <span class="assignee-warn">其他审核员正在处理：{{ rev.assigned_to_name }}</span>
                    </template>
                    <template v-else>
                      <span class="resolved-note">已处理：{{ rev.resolved_by_name || '系统' }}</span>
                    </template>
                  </div>
                </footer>
              </article>
            </div>

            <UiCard v-else class="moderation-empty">
              <strong>当前筛选下没有审核任务</strong>
              <span>需要人工确认的帖子会出现在这里。</span>
            </UiCard>
          </div>

          <!-- Tab 2: Flags -->
          <div v-if="activeTab === 'flags'">
            <div class="section-toolbar">
              <div>
                <span class="panel-kicker">用户举报审核</span>
                <h2>查看举报原因并处理帖子</h2>
              </div>
              <label>
                <span>状态</span>
                <select v-model="statusFilter">
                  <option value="pending">待处理</option>
                  <option value="resolved">已处理</option>
                  <option value="rejected">已驳回</option>
                  <option value="all">全部</option>
                </select>
              </label>
            </div>

            <UiCard v-if="queueQuery.isPending.value" class="moderation-empty moderation-empty--loading">
              <strong>正在加载举报队列</strong>
              <span>请稍候，用户举报加载完成后会显示在这里。</span>
            </UiCard>

            <div v-else-if="flags.length" class="flag-list">
              <article v-for="flag in flags" :key="flag.id" class="flag-card">
                <header>
                  <div>
                    <span class="flag-meta">
                      {{ flagReasonLabel(flag.reason) }} · {{ flagStatusLabel(flag.status) }} ·
                      {{ relativeTime(flag.created_at) }}
                    </span>
                    <h3>{{ flag.target.title }}</h3>
                  </div>
                  <RouterLink :to="targetRoute(flag)">
                    查看上下文
                  </RouterLink>
                </header>

                <div class="report-reason-box">
                  <strong>举报原因：{{ flagReasonLabel(flag.reason) }}</strong>
                  <span>补充说明：{{ flagDetail(flag) }}</span>
                </div>
                <div class="reported-content-box">
                  <strong>被举报内容摘要</strong>
                  <p>{{ flagTargetExcerpt(flag) }}</p>
                </div>
                <dl>
                  <div>
                    <dt>举报人</dt>
                    <dd>{{ flag.reporter_name }}</dd>
                  </div>
                  <div>
                    <dt>作者</dt>
                    <dd>{{ flag.target.author_name }}</dd>
                  </div>
                  <div>
                    <dt>版块</dt>
                    <dd>{{ flag.target.board_name }}</dd>
                  </div>
                  <div>
                    <dt>可见性</dt>
                    <dd>{{ flag.target.hidden ? "已隐藏" : "公开" }}</dd>
                  </div>
                </dl>

                <footer>
                  <UiButton tone="subtle" :disabled="pendingAction" @click="toggleHidden(flag)">
                    {{
                      activeContentPendingFlagId === flag.id
                        ? "处理中…"
                        : flag.target.hidden
                          ? "恢复内容"
                          : "隐藏内容"
                    }}
                  </UiButton>
                  <UiButton tone="success" :disabled="pendingAction" @click="resolveFlag(flag)">
                    {{ activeFlagPendingId === flag.id ? "处理中…" : "标记已处理" }}
                  </UiButton>
                  <UiButton tone="ghost" :disabled="pendingAction" @click="rejectFlag(flag)">
                    {{ activeFlagPendingId === flag.id ? "处理中…" : "驳回举报" }}
                  </UiButton>
                </footer>
              </article>
            </div>

            <UiCard v-else class="moderation-empty">
              <strong>当前筛选下没有举报</strong>
              <span>用户举报主题或回复后，会在这里显示举报原因、说明和被举报内容。</span>
            </UiCard>
          </div>

          <!-- Tab 3: Audit Logs -->
          <div v-if="activeTab === 'audit'">
            <div class="section-toolbar">
              <div>
                <span class="panel-kicker">Audit log</span>
                <h2>全站审计日志</h2>
              </div>
            </div>

            <UiCard v-if="auditQuery.isPending.value" class="moderation-empty moderation-empty--loading">
              <strong>正在加载审计日志</strong>
              <span>请稍候，日志同步完成后会显示在这里。</span>
            </UiCard>

            <UiCard v-else class="audit-panel main-audit-panel">
              <ol v-if="auditLogs.length">
                <li v-for="log in auditLogs" :key="log.id" class="audit-log-item">
                  <div class="log-meta">
                    <strong>{{ auditActionLabel(log.action) }}</strong>
                    <span class="log-time">{{ relativeTime(log.created_at) }}</span>
                  </div>
                  <div class="log-desc">
                    操作人: <span>{{ log.actor_name || "系统" }}</span> ·
                    目标类型: <span>{{ log.target_type }}</span> ·
                    目标 ID: <span>{{ log.target_id }}</span>
                    <span v-if="log.data && Object.keys(log.data).length" class="log-details-block">
                      <br />详情: <code class="log-data-code">{{ JSON.stringify(log.data) }}</code>
                    </span>
                  </div>
                </li>
              </ol>
              <p v-else>暂无审计记录。</p>
            </UiCard>
          </div>
        </main>

        <!-- Sidebar Column (User Management, quick stats) -->
        <aside v-if="activeTab === 'audit'" class="side-column" aria-label="管理工具">
          <UiCard v-if="canUpdateUserStatus" class="user-tool">
            <span class="panel-kicker">管理员操作</span>
            <h2>用户状态调整</h2>
            <label>
              <span>用户 ID</span>
              <input v-model="userId" type="text" placeholder="粘贴 user_id" />
            </label>
            <label>
              <span>状态</span>
              <select v-model="userStatus">
                <option value="silenced">禁言</option>
                <option value="suspended">停用</option>
                <option value="active">恢复 active</option>
              </select>
            </label>
            <label>
              <span>备注</span>
              <textarea v-model="userNote" rows="3" placeholder="记录调整原因" />
            </label>
            <UiButton :disabled="pendingAction || !userId.trim()" @click="updateUser">
              {{ userStatusUpdating ? "更新中…" : "更新用户状态" }}
            </UiButton>
          </UiCard>

          <UiCard v-else class="user-tool">
            <span class="panel-kicker">管理员操作</span>
            <h2>用户状态</h2>
            <p>只有全站管理员可以调整用户状态；版主可以处理帖子发布审核、用户举报和内容可见性。</p>
          </UiCard>
        </aside>
      </section>
    </template>

    <!-- Details Drawer Overlay -->
    <div class="drawer-overlay" :class="{ 'drawer-overlay--open': isDrawerOpen }" @click="closeDrawer">
      <div class="drawer-panel" :class="{ 'drawer-panel--open': isDrawerOpen }" @click.stop>
        <!-- Header -->
        <header class="drawer-header">
          <h3>审核详情</h3>
          <button class="close-btn" @click="closeDrawer">&times;</button>
        </header>

        <!-- Body -->
        <div class="drawer-body" v-if="selectedReviewable">
          <div class="drawer-section">
            <span class="panel-kicker">基本信息</span>
            <div class="meta-grid">
              <div><strong>类型:</strong> {{ reviewableTypeLabel(selectedReviewable.type) }}</div>
              <div><strong>状态:</strong> {{ reviewableStatusLabel(selectedReviewable.status) }}</div>
              <div><strong>时间:</strong> {{ relativeTime(selectedReviewable.created_at) }}</div>
              <div><strong>版块:</strong> {{ selectedReviewable.board_name || '全局' }}</div>
              <div><strong>创建者:</strong> {{ selectedReviewable.created_by_name || '系统' }}</div>
              <div><strong>处理人:</strong> {{ selectedReviewable.assigned_to_name || selectedReviewable.resolved_by_name || '暂无' }}</div>
            </div>
          </div>

          <div class="drawer-section content-preview">
            <span class="panel-kicker">内容预览</span>
            <h4 class="preview-title">{{ reviewableTitle(selectedReviewable) }}</h4>
            <div class="preview-body-box">
              <article v-if="selectedFrontierPreviewCard" class="frontier-preview-card">
                <div class="frontier-preview-card__source">
                  {{ selectedFrontierPreviewCard.source }}
                </div>
                <div
                  class="frontier-preview-card__body"
                  :class="{ 'frontier-preview-card__body--text-only': !selectedFrontierPreviewCard.imageUrl }"
                >
                  <img
                    v-if="selectedFrontierPreviewCard.imageUrl"
                    :src="selectedFrontierPreviewCard.imageUrl"
                    :alt="selectedFrontierPreviewCard.imageAlt || selectedFrontierPreviewCard.title"
                    loading="lazy"
                  />
                  <div class="frontier-preview-card__copy">
                    <a :href="selectedFrontierPreviewCard.url" target="_blank" rel="noopener noreferrer">
                      {{ selectedFrontierPreviewCard.title }}
                    </a>
                    <p>{{ selectedFrontierPreviewCard.summary }}</p>
                  </div>
                </div>
              </article>
              <p v-else class="raw-markdown-view">{{ reviewablePreview(selectedReviewable) }}</p>
            </div>
            <div class="content-appeal-note" v-if="selectedReviewable.data.appeal_reason || selectedReviewable.data.note">
              <strong>复核理由 / 备注:</strong> {{ selectedReviewable.data.appeal_reason || selectedReviewable.data.note }}
            </div>
          </div>

          <!-- History Events -->
          <div class="drawer-section event-history-section">
            <span class="panel-kicker">处理记录</span>
            <div v-if="selectedReviewable.events && selectedReviewable.events.length" class="drawer-events-list">
              <div v-for="event in selectedReviewable.events" :key="event.id" class="drawer-event-item">
                <div class="event-meta">
                  <strong>{{ auditActionLabel(event.event) }}</strong>
                  <span class="event-time">{{ relativeTime(event.created_at) }}</span>
                </div>
                <div class="event-desc">
                  执行人: <span>{{ event.actor_name || '系统' }}</span>
                  <span v-if="event.from_status || event.to_status">
                    （{{ reviewableStatusLabel(event.from_status || '') }} &rarr; {{ reviewableStatusLabel(event.to_status || '') }}）
                  </span>
                </div>
                <div v-if="event.note" class="event-note-quote">“{{ event.note }}”</div>
              </div>
            </div>
            <p v-else class="no-events-desc">暂无处理记录。</p>
          </div>

          <div class="drawer-section operations-form" v-if="canDecideReviewable(selectedReviewable)">
            <span class="panel-kicker">处理决定</span>
            <label class="form-label">
              <span>处理动作</span>
              <select v-model="decisionAction">
                <option value="approve">通过发布</option>
                <option value="reject">拒绝，不发布</option>
                <option value="hide" :disabled="!hasReviewableTarget(selectedReviewable)">隐藏已发布内容</option>
                <option value="delete" :disabled="!hasReviewableTarget(selectedReviewable)">删除已发布内容</option>
                <option value="silence" :disabled="!canSilenceReviewable(selectedReviewable)">禁言作者</option>
                <option value="escalate">暂不处理，升级审核</option>
              </select>
            </label>
            <label class="form-label">
              <span>处理备注 / 决议理由</span>
              <textarea v-model="decisionNote" rows="3" placeholder="可选：写下处理原因，会进入审计记录" />
            </label>
            <div class="form-actions">
              <UiButton tone="success" :disabled="pendingAction" @click="submitDecision">
                {{ activeReviewablePendingId === selectedReviewable.id ? "提交中…" : "提交处理" }}
              </UiButton>
              <UiButton tone="subtle" :disabled="pendingAction" @click="closeDrawer">先不处理</UiButton>
            </div>
          </div>
          <div class="drawer-section operations-form-readonly" v-else-if="isClaimedByOther(selectedReviewable)">
            <span class="panel-kicker">处理决定</span>
            <p class="action-locked-desc">这条内容正在由 <strong>{{ selectedReviewable.assigned_to_name }}</strong> 处理。</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss" src="./ModerationPage.scss"></style>
