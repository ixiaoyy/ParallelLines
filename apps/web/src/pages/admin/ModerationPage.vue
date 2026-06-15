<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  DownOutlined,
  EyeOutlined,
  FlagOutlined,
  FilterOutlined,
  HistoryOutlined,
  LeftOutlined,
  MoreOutlined,
  ReloadOutlined,
  SearchOutlined,
} from "@ant-design/icons-vue";
import { Modal } from "ant-design-vue";

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
  useContentDeleteMutation,
  useContentModerationMutation,
  useFlagStatusMutation,
  useModerationQueue,
  useUserStatusMutation,
  usePublishReviewableQueue,
  useReviewableBulkDecisionMutation,
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
const contentDeleteMutation = useContentDeleteMutation();
const userStatusMutation = useUserStatusMutation();
const currentUserQuery = useCurrentUser();

const decisionMutation = useReviewableDecisionMutation();
const bulkDecisionMutation = useReviewableBulkDecisionMutation();

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
    contentDeleteMutation.isPending.value ||
    userStatusMutation.isPending.value ||
    decisionMutation.isPending.value ||
    bulkDecisionMutation.isPending.value,
);
const activeReviewablePendingId = computed(() =>
  decisionMutation.isPending.value ? activeReviewableId.value : null,
);
const activeFlagPendingId = computed(() =>
  flagStatusMutation.isPending.value ? activeFlagId.value : null,
);
const activeContentPendingFlagId = computed(() =>
  contentMutation.isPending.value || contentDeleteMutation.isPending.value
    ? activeContentFlagId.value
    : null,
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
const selectedReviewableIds = ref<Set<string>>(new Set());
const selectionPointerId = ref<number | null>(null);
const selectionPendingPointerId = ref<number | null>(null);
const selectionPointerValue = ref(true);
const selectionStartPoint = ref<{ x: number; y: number } | null>(null);
const selectionLongPressTimer = ref<number | null>(null);
const suppressReviewableClick = ref(false);
const selectedReviewableIdList = computed(() => Array.from(selectedReviewableIds.value));
const selectedReviewableCount = computed(() => selectedReviewableIds.value.size);
const bulkSelectionActive = computed(() => selectedReviewableCount.value > 0);
const bulkDecisionPending = computed(() => bulkDecisionMutation.isPending.value);
const selectedReviewablesForAction = computed(() =>
  reviewables.value.filter((rev) => selectedReviewableIds.value.has(rev.id)),
);
const selectedReviewablesCanDelete = computed(
  () =>
    selectedReviewablesForAction.value.length > 0 &&
    selectedReviewablesForAction.value.every(canDeleteReviewableTarget),
);

const selectableReviewables = computed(() => reviewables.value.filter(canSelectReviewable));

const isAllSelected = computed(() => {
  const selectables = selectableReviewables.value;
  if (selectables.length === 0) return false;
  return selectables.every((rev) => isReviewableSelected(rev));
});

const isSomeSelected = computed(() => {
  const selectables = selectableReviewables.value;
  if (selectables.length === 0) return false;
  return selectables.some((rev) => isReviewableSelected(rev));
});

function toggleSelectAll() {
  const selectables = selectableReviewables.value;
  if (selectables.length === 0) return;

  if (isAllSelected.value) {
    const nextSelection = new Set(selectedReviewableIds.value);
    for (const rev of selectables) {
      nextSelection.delete(rev.id);
    }
    selectedReviewableIds.value = nextSelection;
  } else {
    const nextSelection = new Set(selectedReviewableIds.value);
    for (const rev of selectables) {
      nextSelection.add(rev.id);
    }
    selectedReviewableIds.value = nextSelection;
  }
}

const REVIEWABLE_LONG_PRESS_MS = 360;
const REVIEWABLE_SCROLL_CANCEL_PX = 12;

watch(
  () => reviewables.value,
  (nextReviewables) => {
    pruneReviewableSelection(nextReviewables);
  },
);

watch(reviewableStatusFilter, () => clearReviewableSelection());

function openReviewableDetails(reviewable: ReviewableResponse) {
  selectedReviewable.value = reviewable;
  decisionAction.value = "approve";
  decisionNote.value = "";
}

// Opens details unless a just-finished long-press selection should consume the
// synthetic click. Key parameter is the clicked reviewable. Return value is
// none. Side effect: may open the reviewable drawer.
function handleReviewableClick(reviewable: ReviewableResponse) {
  if (suppressReviewableClick.value) {
    return;
  }

  openReviewableDetails(reviewable);
}

function closeDrawer() {
  selectedReviewable.value = null;
}

function submitDecision() {
  if (!selectedReviewable.value) return;
  decideReviewable(selectedReviewable.value, decisionAction.value, decisionNote.value, closeDrawer);
}

// Returns whether a reviewable points at already-published content that can be moderated.
// Key parameter `reviewable` is the queue item. Return value is false for queued
// new topics/replies so their contextual topic is not treated as the target.
function hasReviewableTarget(reviewable: ReviewableResponse) {
  const hasPublishedTarget = Boolean(
    reviewable.target_id && ["topic", "post"].includes(reviewable.target_type ?? ""),
  );
  if (!hasPublishedTarget) {
    return false;
  }
  return !["queued_topic", "queued_post"].includes(String(reviewable.type));
}

// Returns whether the current staff user can delete the reviewable's target now.
// Key parameter `reviewable` is a visible queue item. Return value gates destructive
// shortcuts; side effect: none.
function canDeleteReviewableTarget(reviewable: ReviewableResponse) {
  return canDecideReviewable(reviewable) && hasReviewableTarget(reviewable);
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

// Returns whether a reviewable can participate in touch batch selection.
// Key parameter `reviewable` is a visible queue item. Return value is boolean;
// side effect: none.
function canSelectReviewable(reviewable: ReviewableResponse) {
  return canDecideReviewable(reviewable);
}

// Checks selection state for one reviewable id.
// Key parameter `reviewable` is a visible queue item. Return value is boolean;
// side effect: none.
function isReviewableSelected(reviewable: ReviewableResponse) {
  return selectedReviewableIds.value.has(reviewable.id);
}

// Returns the one-based visual selection order shown on selected reviewables.
// Key parameter `reviewable` is a visible queue item. Return value is a display
// index or zero. Side effect: none.
function selectedReviewableNumber(reviewable: ReviewableResponse) {
  return selectedReviewableIdList.value.indexOf(reviewable.id) + 1;
}

// Starts a long-press selection gesture without blocking ordinary page scroll.
// Key parameters are the reviewable and pointer event. Return value is none.
// Side effects: arms a long-press timer and records the starting coordinate.
function beginReviewableSelection(reviewable: ReviewableResponse, event: PointerEvent) {
  if (!canSelectReviewable(reviewable) || isSelectionIgnoredTarget(event.target)) {
    return;
  }
  if (event.pointerType === "mouse" && event.button !== 0) {
    return;
  }

  cancelPendingReviewableSelection();
  const sourceElement = event.currentTarget as HTMLElement;
  selectionPendingPointerId.value = event.pointerId;
  selectionStartPoint.value = { x: event.clientX, y: event.clientY };
  selectionLongPressTimer.value = window.setTimeout(() => {
    if (selectionPendingPointerId.value !== event.pointerId) {
      return;
    }

    selectionPendingPointerId.value = null;
    selectionPointerId.value = event.pointerId;
    selectionPointerValue.value = !isReviewableSelected(reviewable);
    suppressReviewableClick.value = true;
    updateReviewableSelection(reviewable.id, selectionPointerValue.value);
    sourceElement.setPointerCapture?.(event.pointerId);
  }, REVIEWABLE_LONG_PRESS_MS);
}

// Extends active long-press selection, or cancels a pending selection when the
// gesture is clearly a scroll. Key parameter is the pointer event. Return value
// is none. Side effects: mutates selected ids during active selection.
function extendReviewableSelection(event: PointerEvent) {
  if (selectionPendingPointerId.value === event.pointerId && selectionStartPoint.value) {
    const deltaX = event.clientX - selectionStartPoint.value.x;
    const deltaY = event.clientY - selectionStartPoint.value.y;
    if (Math.hypot(deltaX, deltaY) > REVIEWABLE_SCROLL_CANCEL_PX) {
      cancelPendingReviewableSelection();
    }
    return;
  }

  if (selectionPointerId.value !== event.pointerId) {
    return;
  }

  event.preventDefault();
  suppressReviewableClick.value = true;
  const targetId = reviewableIdAtPoint(event.clientX, event.clientY);
  if (!targetId) {
    return;
  }
  const reviewable = reviewables.value.find((item) => item.id === targetId);
  if (!reviewable || !canSelectReviewable(reviewable)) {
    return;
  }

  updateReviewableSelection(targetId, selectionPointerValue.value);
}

// Ends or cancels a long-press selection gesture.
// Key parameter is the pointer event. Return value is none. Side effects:
// clears timer/capture state and suppresses the follow-up click when needed.
function endReviewableSelection(event: PointerEvent) {
  if (selectionPendingPointerId.value === event.pointerId) {
    cancelPendingReviewableSelection();
    return;
  }

  if (selectionPointerId.value !== event.pointerId) {
    return;
  }

  event.preventDefault();
  (event.currentTarget as HTMLElement).releasePointerCapture?.(event.pointerId);
  selectionPointerId.value = null;
  selectionStartPoint.value = null;
  window.setTimeout(() => {
    suppressReviewableClick.value = false;
  }, 0);
}

// Toggles a reviewable through the explicit selector control.
// Key parameter `reviewable` is the queue item being toggled. Return value is
// none. Side effect: replaces `selectedReviewableIds`.
function toggleReviewableSelection(reviewable: ReviewableResponse) {
  if (!canSelectReviewable(reviewable)) {
    return;
  }
  updateReviewableSelection(reviewable.id, !isReviewableSelected(reviewable));
}

// Applies or removes one reviewable id in the immutable selection Set.
// Key parameters are reviewable id and desired selected state. Return value is
// none. Side effect: replaces `selectedReviewableIds`.
function updateReviewableSelection(reviewableId: string, selected: boolean) {
  const nextSelection = new Set(selectedReviewableIds.value);
  if (selected) {
    nextSelection.add(reviewableId);
  } else {
    nextSelection.delete(reviewableId);
  }
  selectedReviewableIds.value = nextSelection;
}

// Clears all selected reviewables.
// Key parameters: none. Return value is none. Side effect: resets selection.
function clearReviewableSelection() {
  selectedReviewableIds.value = new Set();
  cancelPendingReviewableSelection();
  selectionPointerId.value = null;
}

// Drops selected ids that are no longer visible in the current queue data.
// Key parameter `nextReviewables` is the latest visible list. Return value is
// none. Side effect: replaces selection when stale ids are present.
function pruneReviewableSelection(nextReviewables: ReviewableResponse[]) {
  const visibleIds = new Set(nextReviewables.map((reviewable) => reviewable.id));
  const nextSelection = new Set(
    selectedReviewableIdList.value.filter((reviewableId) => visibleIds.has(reviewableId)),
  );
  if (nextSelection.size !== selectedReviewableIds.value.size) {
    selectedReviewableIds.value = nextSelection;
  }
}

// Clears the pending long-press timer before it becomes a selection gesture.
// Key parameters: none. Return value is none. Side effects: resets pending
// pointer bookkeeping and cancels the browser timer.
function cancelPendingReviewableSelection() {
  if (selectionLongPressTimer.value !== null) {
    window.clearTimeout(selectionLongPressTimer.value);
  }
  selectionLongPressTimer.value = null;
  selectionPendingPointerId.value = null;
  selectionStartPoint.value = null;
}

// Finds a reviewable card id at viewport coordinates during drag selection.
// Key parameters are pointer x/y coordinates. Return value is the reviewable id
// or null. Side effect: none.
function reviewableIdAtPoint(clientX: number, clientY: number) {
  const element = document
    .elementFromPoint(clientX, clientY)
    ?.closest<HTMLElement>("[data-reviewable-id]");
  return element?.dataset.reviewableId ?? null;
}

// Checks whether a pointer target belongs to an interactive child control.
// Key parameter is the raw pointer target. Return value is boolean; side effect:
// none.
function isSelectionIgnoredTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  return Boolean(
    target.closest(
      "button,a,input,select,textarea,[role='button'],[data-selection-ignore='true']",
    ),
  );
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
    return "小小资讯自动采集并整理；审核通过后会直接发布到热点资讯版块。";
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
    const previewCard = frontierPreviewCard(reviewable);
    if (previewCard) {
      return previewCard.summary;
    }

    const rawMarkdown = textField(reviewable.data.raw_md);
    const previewMarkdown = rawMarkdown
      .replace(/(^|\n):::\s*news-card\s*(?=\n|$)/g, "")
      .replace(/(^|\n):::\s*(?=\n|$)/g, "")
      .replace(/(^|\n)\s*一句话[：:].*(?=\n|$)/g, "")
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
    return parseFrontierNewsCard(rawMarkdown) ?? parseLegacyFrontierNewsCard(rawMarkdown, reviewable);
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
      if (/^一句话[：:]/.test(line)) {
        continue;
      }
      const summaryLine = line.trim();
      if (!summaryLine || /^(原文|来源)[：:]/.test(summaryLine)) {
        continue;
      }
      summaryLines.push(summaryLine);
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
  )
    .replace(/^一句话[：:]\s*/, "")
    .trim();
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

// Deletes the already-published target attached to one reviewable after confirmation.
// Key parameter `reviewable` is the queue item being handled. Return value is none;
// side effect: submits a destructive moderation decision and refreshes queues.
function deleteReviewable(reviewable: ReviewableResponse) {
  if (!canDeleteReviewableTarget(reviewable)) {
    actionError.value = "这条审核项没有可删除的已发布内容。";
    return;
  }
  Modal.confirm({
    title: "删除这条已发布内容？",
    content: "删除后会从公开页面隐藏，并在审核记录中留下操作痕迹。",
    okText: "删除",
    cancelText: "取消",
    okType: "danger",
    onOk: () => decideReviewable(reviewable, "delete", "审核删除已发布内容。"),
  });
}

// Submits the current selected reviewables as one backend batch decision.
// Key parameters are the moderation action and note. Return value is none.
// Side effects: mutates backend reviewables and clears selection on success.
function submitBulkReviewableDecision(action: ReviewableDecisionAction, note: string) {
  if (!selectedReviewableIdList.value.length || bulkDecisionPending.value) {
    return;
  }

  resetActionFeedback();
  bulkDecisionMutation.mutate(
    {
      reviewable_ids: selectedReviewableIdList.value,
      action,
      note,
    },
    {
      onSuccess: (response) => {
        actionNotice.value = `${bulkDecisionLabel(action)}：已处理 ${response.processed_count} 条。`;
        clearReviewableSelection();
      },
      onError: (error) => {
        actionError.value = mutationErrorMessage(error);
      },
    },
  );
}

// Deletes all selected reviewables that point at published targets after confirmation.
// Key parameters: none. Return value is none. Side effect: submits the existing
// bulk reviewable decision endpoint with the destructive delete action.
function submitBulkDeleteReviewables() {
  if (!selectedReviewablesCanDelete.value) {
    actionError.value = "只能批量删除已发布内容；待审新帖请使用驳回。";
    return;
  }
  Modal.confirm({
    title: `删除已选 ${selectedReviewableCount.value} 条内容？`,
    content: "这些已发布内容会从公开页面隐藏，并按批量审核删除记录处理。",
    okText: "批量删除",
    cancelText: "取消",
    okType: "danger",
    onOk: () => submitBulkReviewableDecision("delete", "批量审核删除已发布内容。"),
  });
}

// Returns the operator-facing label for a bulk moderation action.
// Key parameter `action` is the submitted decision. Return value is display
// text. Side effect: none.
function bulkDecisionLabel(action: ReviewableDecisionAction) {
  const labels: Record<ReviewableDecisionAction, string> = {
    approve: "一键通过",
    reject: "批量驳回",
    hide: "批量隐藏",
    delete: "批量删除",
    silence: "批量禁言",
    escalate: "人工复核",
  };
  return labels[action];
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

// Deletes the reported content from the flag queue after explicit confirmation.
// Key parameter `flag` provides the target id/type from the current queue row.
// Return value is none; side effect: hides topics or erases post bodies.
function deleteFlagTarget(flag: FlagResponse) {
  Modal.confirm({
    title: "删除这条被举报内容？",
    content: "删除后会从公开页面隐藏，举报队列会在接口完成后刷新。",
    okText: "删除",
    cancelText: "取消",
    okType: "danger",
    onOk: () => {
      resetActionFeedback();
      activeContentFlagId.value = flag.id;
      contentDeleteMutation.mutate({
        targetType: flag.target.target_type,
        targetId: flag.target.target_id,
        note: "审核台删除内容。",
      }, {
        onSuccess: () => {
          actionNotice.value = `${flag.target.title}：已删除内容。`;
        },
        onError: (error) => {
          actionError.value = mutationErrorMessage(error);
        },
        onSettled: () => {
          activeContentFlagId.value = null;
        },
      });
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
        <p>这里分两件事：审核内容是否发布；查看用户举报原因，并处理被举报的主题或楼层。</p>
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
      <div class="reviewable-mobile-appbar" aria-label="内容审核移动端工具栏">
        <RouterLink class="reviewable-mobile-appbar__icon" to="/admin" aria-label="返回后台">
          <LeftOutlined />
        </RouterLink>
        <strong>发布审核</strong>
        <div class="reviewable-mobile-appbar__actions">
          <button type="button" class="reviewable-mobile-appbar__icon" aria-label="搜索审核内容">
            <SearchOutlined />
          </button>
          <button type="button" class="reviewable-mobile-appbar__filter" aria-label="筛选审核内容">
            <span>筛选</span>
            <FilterOutlined />
          </button>
        </div>
      </div>

      <!-- Navigation Tabs -->
      <nav class="moderation-tabs" aria-label="审核台导航">
        <button :class="{ active: activeTab === 'reviewables' }" @click="activeTab = 'reviewables'">
          <EyeOutlined /> 内容发布审核
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
            <div class="reviewable-mobile-reviewbar" aria-label="内容审核状态">
              <button
                type="button"
                class="reviewable-mobile-reviewbar__tab"
                :class="{ active: reviewableStatusFilter === 'pending' }"
                @click="reviewableStatusFilter = 'pending'"
              >
                <span>待处理</span>
                <b>{{ reviewableStatusFilter === 'pending' ? reviewables.length : "·" }}</b>
              </button>
              <button
                type="button"
                class="reviewable-mobile-reviewbar__tab"
                :class="{ active: bulkSelectionActive }"
              >
                <span>已选</span>
                <b>{{ selectedReviewableCount }}</b>
              </button>
              <button
                type="button"
                class="reviewable-mobile-reviewbar__tab"
                :class="{ active: reviewableStatusFilter === 'approved' }"
                @click="reviewableStatusFilter = 'approved'"
              >
                <span>已通过</span>
                <b>{{ reviewableStatusFilter === 'approved' ? reviewables.length : "" }}</b>
              </button>
            </div>

            <div class="reviewable-mobile-filterbar" aria-label="内容审核筛选">
              <button type="button">
                <FilterOutlined />
                <span>筛选</span>
              </button>
              <button type="button">
                <span>排序：最新发布</span>
                <DownOutlined />
              </button>
              <button type="button" aria-label="刷新审核队列" @click="reviewablesQuery.refetch()">
                <ReloadOutlined />
              </button>
            </div>

            <div class="section-toolbar">
              <div>
                <span class="panel-kicker">内容发布审核</span>
                <h2>审核待发布的内容</h2>
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

            <template v-else-if="reviewables.length">
              <div v-if="selectableReviewables.length" class="list-operations-bar">
                <label class="select-all-label">
                  <input
                    type="checkbox"
                    :checked="isAllSelected"
                    :indeterminate="isSomeSelected && !isAllSelected"
                    @change="toggleSelectAll"
                  />
                  <span>全选当前页 (已选 {{ selectedReviewableCount }} / {{ selectableReviewables.length }} 条可处理)</span>
                </label>
                <button
                  v-if="bulkSelectionActive"
                  type="button"
                  class="clear-selection-btn"
                  @click="clearReviewableSelection"
                >
                  取消选择
                </button>
              </div>

              <ol class="reviewable-list">
                <li
                  v-for="rev in reviewables"
                  :key="rev.id"
                  class="reviewable-list-item"
                  :class="{
                    'reviewable-list-item--selected': isReviewableSelected(rev),
                    'reviewable-list-item--disabled': !canSelectReviewable(rev),
                  }"
                  :data-reviewable-id="rev.id"
                  @click="handleReviewableClick(rev)"
                  @pointerdown="beginReviewableSelection(rev, $event)"
                  @pointermove="extendReviewableSelection"
                  @pointerup="endReviewableSelection"
                  @pointercancel="endReviewableSelection"
                >
                  <button
                    type="button"
                    class="reviewable-list-item__selector"
                    :class="{ 'reviewable-list-item__selector--active': isReviewableSelected(rev) }"
                    :disabled="!canSelectReviewable(rev)"
                    :aria-label="isReviewableSelected(rev) ? '取消选择审核项' : '选择审核项'"
                    data-selection-ignore="true"
                    @pointerdown.stop
                    @click.stop="toggleReviewableSelection(rev)"
                  >
                    <template v-if="isReviewableSelected(rev)">{{ selectedReviewableNumber(rev) }}</template>
                  </button>
                  <button
                    type="button"
                    class="reviewable-list-item__menu"
                    aria-label="打开审核项操作"
                    data-selection-ignore="true"
                    @pointerdown.stop
                    @click.stop="openReviewableDetails(rev)"
                  >
                    <MoreOutlined />
                  </button>
                  <div class="reviewable-list-item__main">
                    <span class="reviewable-list-item__meta">
                      {{ reviewableStatusLabel(rev.status) }} ·
                      {{ rev.board_name || '全局' }} ·
                      {{ rev.target_user_name || rev.created_by_name || '系统' }} ·
                      {{ relativeTime(rev.created_at) }}
                    </span>
                    <h3>{{ reviewableTitle(rev) }}</h3>
                    <p>{{ reviewablePreview(rev) }}</p>
                  </div>

                  <div class="reviewable-list-item__actions">
                    <template v-if="canDecideReviewable(rev)">
                      <UiButton
                        tone="danger"
                        :disabled="pendingAction"
                        data-selection-ignore="true"
                        @pointerdown.stop
                        @click.stop="rejectReviewable(rev)"
                      >
                        {{ activeReviewablePendingId === rev.id ? "处理中…" : "驳回" }}
                      </UiButton>
                      <UiButton
                        v-if="canDeleteReviewableTarget(rev)"
                        tone="danger"
                        :disabled="pendingAction"
                        data-selection-ignore="true"
                        @pointerdown.stop
                        @click.stop="deleteReviewable(rev)"
                      >
                        {{ activeReviewablePendingId === rev.id ? "处理中…" : "删除" }}
                      </UiButton>
                      <UiButton
                        tone="success"
                        :disabled="pendingAction"
                        data-selection-ignore="true"
                        @pointerdown.stop
                        @click.stop="approveReviewable(rev)"
                      >
                        {{ activeReviewablePendingId === rev.id ? "处理中…" : "通过" }}
                      </UiButton>
                      <UiButton
                        tone="subtle"
                        :disabled="pendingAction"
                        data-selection-ignore="true"
                        @pointerdown.stop
                        @click.stop="openReviewableDetails(rev)"
                      >
                        详情
                      </UiButton>
                    </template>
                    <template v-else-if="isClaimedByOther(rev)">
                      <span class="assignee-warn">处理中：{{ rev.assigned_to_name }}</span>
                      <UiButton
                        tone="subtle"
                        :disabled="pendingAction"
                        data-selection-ignore="true"
                        @pointerdown.stop
                        @click.stop="openReviewableDetails(rev)"
                      >
                        详情
                      </UiButton>
                    </template>
                    <template v-else>
                      <span class="resolved-note">已处理：{{ rev.resolved_by_name || '系统' }}</span>
                      <UiButton
                        tone="subtle"
                        :disabled="pendingAction"
                        data-selection-ignore="true"
                        @pointerdown.stop
                        @click.stop="openReviewableDetails(rev)"
                      >
                        详情
                      </UiButton>
                    </template>
                  </div>
                </li>
              </ol>
            </template>

            <Transition name="bulk-bar">
              <div v-if="bulkSelectionActive" class="reviewable-bulk-bar" role="status" aria-live="polite">
                <div class="reviewable-bulk-bar__summary">
                  <strong>已选 {{ selectedReviewableCount }} 条</strong>
                  <span>{{ reviewableStatusLabel(reviewableStatusFilter === 'all' ? 'pending' : reviewableStatusFilter) }}</span>
                </div>
                <div class="reviewable-bulk-bar__actions">
                  <UiButton
                    tone="success"
                    :disabled="bulkDecisionPending"
                    @click="submitBulkReviewableDecision('approve', '批量审核通过，允许发布。')"
                  >
                    {{ bulkDecisionPending ? "处理中…" : "通过" }}
                  </UiButton>
                  <UiButton
                    tone="ghost"
                    :disabled="bulkDecisionPending"
                    @click="submitBulkReviewableDecision('reject', '批量审核拒绝，不予发布。')"
                  >
                    驳回
                  </UiButton>
                  <UiButton
                    tone="subtle"
                    :disabled="bulkDecisionPending"
                    @click="submitBulkReviewableDecision('escalate', '批量升级为人工复核。')"
                  >
                    人工复核
                  </UiButton>
                  <UiButton
                    tone="danger"
                    :disabled="bulkDecisionPending || !selectedReviewablesCanDelete"
                    title="只支持删除已发布内容；待审新帖请使用驳回"
                    @click="submitBulkDeleteReviewables"
                  >
                    删除
                  </UiButton>
                  <UiButton tone="ghost" :disabled="bulkDecisionPending" @click="clearReviewableSelection">
                    取消
                  </UiButton>
                </div>
              </div>
            </Transition>

            <UiCard v-if="!reviewablesQuery.isPending.value && !reviewables.length" class="moderation-empty">
              <strong>当前筛选下没有审核任务</strong>
              <span>需要人工确认的主题、回复或编辑会出现在这里。</span>
            </UiCard>
          </div>

          <!-- Tab 2: Flags -->
          <div v-if="activeTab === 'flags'">
            <div class="section-toolbar">
              <div>
                <span class="panel-kicker">用户举报审核</span>
                <h2>查看举报原因并处理内容</h2>
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
                  <UiButton tone="danger" :disabled="pendingAction" @click="deleteFlagTarget(flag)">
                    {{ activeContentPendingFlagId === flag.id ? "处理中…" : "删除内容" }}
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
            <p>只有全站管理员可以调整用户状态；版主可以处理内容发布审核、用户举报和内容可见性。</p>
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
