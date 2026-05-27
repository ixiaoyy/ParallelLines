<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import type { BoardSummary } from "@/entities/board/model";
import SimilarTopicHints from "@/features/ai/components/SimilarTopicHints.vue";
import { useBoards } from "@/features/boards/queries";
import { useCreateTopic } from "@/features/topics/queries";
import { useSaveDraft, useDeleteDraft } from "@/features/drafts/queries";
import { lookupDraft } from "@/features/drafts/api";
import type { DraftResponse } from "@/features/drafts/model";
import MarkdownUploadButton from "@/features/uploads/components/MarkdownUploadButton.vue";
import { contentPolicyMessage } from "@/shared/api/errors";
import { compactNumber } from "@/shared/lib/format";
import { readRouteParam } from "@/shared/router/params";
import { boardToneClass } from "@/shared/theme/boardPalette";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import { ApiError, hasAccessToken } from "@/shared/api/client";
import { isApiErrorCode } from "@/shared/api/errors";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

type TopicIntent = "question" | "bug" | "idea" | "guide";

type PublishState = "idle" | "saved" | "submitted";

interface NewTopicDraft {
  boardSlug: string;
  intent: TopicIntent;
  title: string;
  body: string;
  tags: string;
  pollEnabled: boolean;
  pollQuestion: string;
  pollOptions: string;
  pollMultipleChoice: boolean;
  pollClosesAt: string;
  version: number;
}

const DRAFT_STORAGE_KEY = "parallellines:new-topic-draft";

const route = useRoute();
const router = useRouter();
const boardsQuery = useBoards();
const createTopic = useCreateTopic();
const saveDraftMutation = useSaveDraft();
const deleteDraftMutation = useDeleteDraft();

const sectionLinks = [
  { id: "board", label: "选择版块", helper: "先找对问题区" },
  { id: "title", label: "标题", helper: "症状 + 环境" },
  { id: "content", label: "正文", helper: "日志与复现" },
  { id: "tags", label: "标签", helper: "方便检索" },
  { id: "poll", label: "投票", helper: "收集选择" },
  { id: "preview", label: "预览检查", helper: "确认可回答" },
  { id: "drafts", label: "草稿", helper: "自动保存" },
];

const topicIntents: Array<{ key: TopicIntent; label: string; helper: string }> = [
  { key: "question", label: "我要排障", helper: "报错、安装、升级、登录问题" },
  { key: "bug", label: "确认缺陷", helper: "可复现路径和影响范围" },
  { key: "idea", label: "功能提案", helper: "收益、成本、备选方案" },
  { key: "guide", label: "经验复盘", helper: "沉淀步骤和结论" },
];

const defaultDraft: Omit<NewTopicDraft, "version"> = {
  boardSlug: "support",
  intent: "question",
  title: "",
  body: "",
  tags: "",
  pollEnabled: false,
  pollQuestion: "",
  pollOptions: "",
  pollMultipleChoice: false,
  pollClosesAt: "",
};

const selectedBoardSlug = ref(defaultDraft.boardSlug);
const selectedIntent = ref<TopicIntent>(defaultDraft.intent);
const title = ref(defaultDraft.title);
const body = ref(defaultDraft.body);
const tags = ref(defaultDraft.tags);
const pollEnabled = ref(defaultDraft.pollEnabled);
const pollQuestion = ref(defaultDraft.pollQuestion);
const pollOptions = ref(defaultDraft.pollOptions);
const pollMultipleChoice = ref(defaultDraft.pollMultipleChoice);
const pollClosesAt = ref(defaultDraft.pollClosesAt);
const currentVersion = ref(1);

const bodyTextarea = ref<HTMLTextAreaElement | null>(null);
const publishState = ref<PublishState>("idle");
const publishError = ref("");
const showConflictBanner = ref(false);
const isSaving = ref(false);

const boardOptions = computed(() => boardsQuery.data.value ?? []);
const publishableBoardOptions = computed(() =>
  boardOptions.value.filter((board) => board.canCreateTopic),
);
const selectedBoard = computed(
  () => boardOptions.value.find((board) => board.slug === selectedBoardSlug.value) ?? boardOptions.value[0],
);
const selectedBoardCanCreateTopic = computed(() => Boolean(selectedBoard.value?.canCreateTopic));

const parsedTags = computed(() =>
  tags.value
    .split(/[，,]/)
    .map((tag) => tag.trim())
    .filter(Boolean)
    .slice(0, 6),
);
const missingRequiredTags = computed(() => {
  const required = selectedBoard.value?.requiredTags ?? [];
  return required.filter((tag) => !parsedTags.value.includes(tag));
});
const disallowedTags = computed(() => {
  const allowed = selectedBoard.value?.allowedTags ?? [];
  if (!allowed.length) {
    return [];
  }

  return parsedTags.value.filter((tag) => !allowed.includes(tag));
});
const tagPolicyHint = computed(() => {
  const required = selectedBoard.value?.requiredTags ?? [];
  const allowed = selectedBoard.value?.allowedTags ?? [];
  if (required.length) {
    return `必填：${required.map((tag) => `#${tag}`).join(" ")}${
      allowed.length ? `；允许：${allowed.map((tag) => `#${tag}`).join(" ")}` : ""
    }`;
  }

  if (allowed.length) {
    return `该版块只允许：${allowed.map((tag) => `#${tag}`).join(" ")}`;
  }

  return "该版块未限制标签；建议至少补充 1 个可检索标签。";
});

const parsedPollOptions = computed(() =>
  pollOptions.value
    .split(/\r?\n/)
    .map((option) => option.trim())
    .filter(Boolean)
    .slice(0, 12),
);
const pollReady = computed(
  () =>
    !pollEnabled.value ||
    (pollQuestion.value.trim().length >= 4 && parsedPollOptions.value.length >= 2),
);

const checklist = computed(() => [
  { label: "已选择版块", done: Boolean(selectedBoard.value) },
  { label: "当前版块允许发帖", done: selectedBoardCanCreateTopic.value },
  { label: "标题不少于 12 个字", done: title.value.trim().length >= 12 },
  { label: "正文包含复现/背景", done: body.value.trim().length >= 40 },
  {
    label: selectedBoard.value?.requiredTags.length ? "必填标签已补齐" : "至少 1 个标签",
    done: selectedBoard.value?.requiredTags.length
      ? missingRequiredTags.value.length === 0
      : parsedTags.value.length > 0,
  },
  {
    label: "标签符合版块范围",
    done: disallowedTags.value.length === 0,
  },
  {
    label: pollEnabled.value ? "Poll 至少 2 个选项" : "无需 Poll",
    done: pollReady.value,
  },
]);

const completion = computed(() => checklist.value.filter((item) => item.done).length);
const remainingChecklist = computed(() => checklist.value.filter((item) => !item.done));
const completionNote = computed(() => {
  if (!remainingChecklist.value.length) {
    return "已满足发布条件";
  }

  const visibleItems = remainingChecklist.value.slice(0, 2).map((item) => item.label);
  const suffix = remainingChecklist.value.length > visibleItems.length ? "等" : "";
  return `还差：${visibleItems.join("、")}${suffix}`;
});
const canPublish = computed(() => checklist.value.every((item) => item.done));
const draftStatus = computed(() => {
  if (publishState.value === "submitted") {
    return "已生成发布预览";
  }

  if (isSaving.value) {
    return "同步中...";
  }

  if (publishState.value === "saved") {
    return "草稿已保存";
  }

  return "正在编辑";
});

const previewBody = computed(() =>
  body.value.trim() || "正文预览会显示在这里。建议包含：环境、错误信息、复现步骤、已经尝试过的方法。",
);

let isRestoring = false;

watch(selectedBoard, (board) => {
  if (!board || isRestoring || body.value.trim() || !board.postTemplate) {
    return;
  }

  body.value = board.postTemplate;
});

onMounted(async () => {
  isRestoring = true;
  const localDraft = readSavedDraft();
  let serverDraft: DraftResponse | null = null;

  if (hasAccessToken()) {
    try {
      serverDraft = await lookupDraft("new_topic", "");
    } catch (e) {
      console.error("Failed to fetch server draft on mount", e);
    }
  }

  if (localDraft && serverDraft) {
    const localVer = localDraft.version ?? 1;
    const serverVer = serverDraft.version;

    if (localVer > serverVer) {
      loadDraftState(localVerDraft(localDraft));
      void performServerSave();
    } else if (serverVer > localVer) {
      loadDraftState(serverDraftToLocal(serverDraft));
      saveLocalDraft();
    } else {
      const mappedServer = serverDraftToLocal(serverDraft);
      if (isDraftEqual(localDraft, mappedServer)) {
        loadDraftState(localDraft);
      } else {
        loadDraftState(localDraft);
        void performServerSave();
      }
    }
  } else if (localDraft) {
    loadDraftState(localVerDraft(localDraft));
    if (hasAccessToken()) {
      void performServerSave();
    }
  } else if (serverDraft) {
    loadDraftState(serverDraftToLocal(serverDraft));
    saveLocalDraft();
  } else {
    loadDraftState({
      boardSlug: defaultDraft.boardSlug,
      intent: defaultDraft.intent,
      title: defaultDraft.title,
      body: defaultDraft.body,
      tags: defaultDraft.tags,
      pollEnabled: defaultDraft.pollEnabled,
      pollQuestion: defaultDraft.pollQuestion,
      pollOptions: defaultDraft.pollOptions,
      pollMultipleChoice: defaultDraft.pollMultipleChoice,
      pollClosesAt: defaultDraft.pollClosesAt,
      version: 1,
    });
    saveLocalDraft();
  }

  nextTick(() => {
    isRestoring = false;
  });
});

watch(
  boardOptions,
  (options) => {
    const queryBoard = readRouteParam(route.query.board as string | string[] | undefined);
    if (options.some((board) => board.slug === queryBoard && board.canCreateTopic)) {
      selectedBoardSlug.value = queryBoard;
      return;
    }

    if (
      publishableBoardOptions.value.length &&
      !publishableBoardOptions.value.some((board) => board.slug === selectedBoardSlug.value)
    ) {
      selectedBoardSlug.value = publishableBoardOptions.value[0].slug;
    }
  },
  { immediate: true },
);

watch([selectedBoardSlug, selectedIntent, title, body, tags, pollEnabled, pollQuestion, pollOptions, pollMultipleChoice, pollClosesAt], () => {
  if (isRestoring) {
    return;
  }
  triggerAutosave();
});

function chooseBoard(board: BoardSummary) {
  if (!board.canCreateTopic) {
    publishError.value = "官方动态仅管理员可以发布主题；普通用户可以浏览、回复、收藏和复制链接。";
    return;
  }

  selectedBoardSlug.value = board.slug;
  publishError.value = "";
}

function chooseIntent(intent: TopicIntent) {
  selectedIntent.value = intent;
}

function addTag(tag: string) {
  const currentTags = parsedTags.value;
  if (currentTags.includes(tag)) {
    return;
  }

  tags.value = [...currentTags, tag].join(", ");
}

function localVerDraft(local: NewTopicDraft): NewTopicDraft {
  return {
    boardSlug: local.boardSlug,
    intent: local.intent,
    title: local.title,
    body: local.body,
    tags: local.tags,
    pollEnabled: local.pollEnabled ?? defaultDraft.pollEnabled,
    pollQuestion: local.pollQuestion ?? defaultDraft.pollQuestion,
    pollOptions: local.pollOptions ?? defaultDraft.pollOptions,
    pollMultipleChoice: local.pollMultipleChoice ?? defaultDraft.pollMultipleChoice,
    pollClosesAt: local.pollClosesAt ?? defaultDraft.pollClosesAt,
    version: local.version ?? 1,
  };
}

function serverDraftToLocal(server: DraftResponse): NewTopicDraft {
  return {
    boardSlug: (server.data.boardSlug as string) ?? defaultDraft.boardSlug,
    intent: (server.data.intent as TopicIntent) ?? defaultDraft.intent,
    title: (server.data.title as string) ?? defaultDraft.title,
    body: (server.data.body as string) ?? defaultDraft.body,
    tags: (server.data.tags as string) ?? defaultDraft.tags,
    pollEnabled: (server.data.pollEnabled as boolean) ?? defaultDraft.pollEnabled,
    pollQuestion: (server.data.pollQuestion as string) ?? defaultDraft.pollQuestion,
    pollOptions: (server.data.pollOptions as string) ?? defaultDraft.pollOptions,
    pollMultipleChoice: (server.data.pollMultipleChoice as boolean) ?? defaultDraft.pollMultipleChoice,
    pollClosesAt: (server.data.pollClosesAt as string) ?? defaultDraft.pollClosesAt,
    version: server.version,
  };
}

function isDraftEqual(a: NewTopicDraft, b: NewTopicDraft) {
  return (
    a.boardSlug === b.boardSlug &&
    a.intent === b.intent &&
    a.title === b.title &&
    a.body === b.body &&
    a.tags === b.tags &&
    a.pollEnabled === b.pollEnabled &&
    a.pollQuestion === b.pollQuestion &&
    a.pollOptions === b.pollOptions &&
    a.pollMultipleChoice === b.pollMultipleChoice &&
    a.pollClosesAt === b.pollClosesAt
  );
}

function loadDraftState(draft: NewTopicDraft) {
  isRestoring = true;
  selectedBoardSlug.value = draft.boardSlug;
  selectedIntent.value = draft.intent;
  title.value = draft.title;
  body.value = draft.body;
  tags.value = draft.tags;
  pollEnabled.value = draft.pollEnabled;
  pollQuestion.value = draft.pollQuestion;
  pollOptions.value = draft.pollOptions;
  pollMultipleChoice.value = draft.pollMultipleChoice;
  pollClosesAt.value = draft.pollClosesAt;
  currentVersion.value = draft.version ?? 1;

  nextTick(() => {
    isRestoring = false;
  });
}

let saveTimeout: ReturnType<typeof setTimeout> | null = null;

function triggerAutosave() {
  saveLocalDraft();

  if (!hasAccessToken()) {
    return;
  }

  if (saveTimeout) {
    clearTimeout(saveTimeout);
  }

  publishState.value = "idle";

  saveTimeout = setTimeout(async () => {
    await performServerSave();
  }, 1000);
}

async function performServerSave() {
  if (isSaving.value) {
    if (saveTimeout) clearTimeout(saveTimeout);
    saveTimeout = setTimeout(performServerSave, 500);
    return;
  }

  isSaving.value = true;
  const nextVersion = currentVersion.value + 1;

  try {
    const draftPayload = {
      boardSlug: selectedBoardSlug.value,
      intent: selectedIntent.value,
      title: title.value,
      body: body.value,
      tags: tags.value,
      pollEnabled: pollEnabled.value,
      pollQuestion: pollQuestion.value,
      pollOptions: pollOptions.value,
      pollMultipleChoice: pollMultipleChoice.value,
      pollClosesAt: pollClosesAt.value,
    };

    const result = await saveDraftMutation.mutateAsync({
      target_type: "new_topic",
      target_id: "",
      draft_type: "topic",
      data: draftPayload,
      version: nextVersion,
    });

    currentVersion.value = result.version;
    publishState.value = "saved";
    saveLocalDraft();
  } catch (error: unknown) {
    if (isApiErrorCode(error, "draft_conflict")) {
      await handleDraftConflict();
    } else {
      console.error("Autosave failed:", error);
    }
  } finally {
    isSaving.value = false;
  }
}

async function handleDraftConflict() {
  showConflictBanner.value = true;
  setTimeout(() => {
    showConflictBanner.value = false;
  }, 5000);

  try {
    const serverDraft = await lookupDraft("new_topic", "");
    if (serverDraft) {
      loadDraftState(serverDraftToLocal(serverDraft));
      saveLocalDraft();
    }
  } catch (err) {
    console.error("Failed to recover from draft conflict:", err);
  }
}

async function handleSaveDraft() {
  saveLocalDraft();
  if (hasAccessToken()) {
    if (saveTimeout) {
      clearTimeout(saveTimeout);
    }
    publishState.value = "idle";
    await performServerSave();
  } else {
    publishState.value = "saved";
  }
}

function insertMarkdownUpload(markdown: string) {
  const textarea = bodyTextarea.value;
  if (!textarea) {
    body.value = [body.value.trimEnd(), markdown].filter(Boolean).join("\n\n");
    return;
  }

  const start = textarea.selectionStart ?? body.value.length;
  const end = textarea.selectionEnd ?? start;
  const before = body.value.slice(0, start);
  const after = body.value.slice(end);
  const leadingBreak = before && !before.endsWith("\n") ? "\n\n" : "";
  const trailingBreak = after && !after.startsWith("\n") ? "\n\n" : "";
  const insert = `${leadingBreak}${markdown}${trailingBreak}`;
  body.value = `${before}${insert}${after}`;
  const cursor = before.length + insert.length;
  void nextTick(() => {
    textarea.focus();
    textarea.setSelectionRange(cursor, cursor);
  });
}

async function handleSubmit() {
  if (!canPublish.value) {
    if (!selectedBoardCanCreateTopic.value) {
      publishError.value = "官方动态仅管理员可以发布主题；请选择其他版块。";
      publishState.value = "submitted";
    }
    return;
  }

  if (saveTimeout) {
    clearTimeout(saveTimeout);
  }

  publishError.value = "";

  try {
    const topic = await createTopic.mutateAsync({
      boardSlug: selectedBoardSlug.value,
      payload: {
        title: title.value.trim(),
        raw_md: body.value.trim(),
        tags: parsedTags.value,
        poll: pollEnabled.value
          ? {
              question: pollQuestion.value.trim(),
              options: parsedPollOptions.value,
              multiple_choice: pollMultipleChoice.value,
              closes_at: pollClosesAt.value ? new Date(pollClosesAt.value).toISOString() : null,
            }
          : null,
      },
    });

    if (hasAccessToken()) {
      try {
        await deleteDraftMutation.mutateAsync({ targetType: "new_topic", targetId: "" });
      } catch (e) {
        console.error("Failed to delete draft on server", e);
      }
    }
    window.localStorage.removeItem(DRAFT_STORAGE_KEY);
    await router.push(topicDetailRoute(topic));
  } catch (error) {
    publishState.value = "submitted";
    publishError.value = boardPolicyMessage(error) ?? contentPolicyMessage(
      error,
      "当前未登录或服务暂时不可用，已保留为发布预览；登录后可再次提交。",
    );
  }
}

function boardPolicyMessage(error: unknown): string | null {
  if (error instanceof ApiError && error.code === "required_tags_missing") {
    const missing = Array.isArray(error.details.missing_tags)
      ? error.details.missing_tags.join("、")
      : "必填标签";
    return `请补齐版块必填标签：${missing}。`;
  }

  if (error instanceof ApiError && error.code === "tag_not_allowed") {
    const disallowed = Array.isArray(error.details.disallowed_tags)
      ? error.details.disallowed_tags.join("、")
      : "不允许的标签";
    return `该版块不允许使用这些标签：${disallowed}。`;
  }

  if (error instanceof ApiError && error.code === "board_topic_create_restricted") {
    return "官方动态仅管理员可以发布主题；普通用户可以浏览、回复、收藏和复制链接。";
  }

  return null;
}

function saveLocalDraft() {
  if (typeof window === "undefined") {
    return;
  }

  const draft: NewTopicDraft = {
    boardSlug: selectedBoardSlug.value,
    intent: selectedIntent.value,
    title: title.value,
    body: body.value,
    tags: tags.value,
    pollEnabled: pollEnabled.value,
    pollQuestion: pollQuestion.value,
    pollOptions: pollOptions.value,
    pollMultipleChoice: pollMultipleChoice.value,
    pollClosesAt: pollClosesAt.value,
    version: currentVersion.value,
  };

  window.localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
}

function readSavedDraft() {
  if (typeof window === "undefined") {
    return null;
  }

  const rawDraft = window.localStorage.getItem(DRAFT_STORAGE_KEY);

  if (!rawDraft) {
    return null;
  }

  try {
    const value: unknown = JSON.parse(rawDraft);

    if (!isDraft(value)) {
      return null;
    }

    return value;
  } catch {
    return null;
  }
}

function isDraft(value: unknown): value is NewTopicDraft {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.boardSlug === "string" &&
    isTopicIntent(value.intent) &&
    typeof value.title === "string" &&
    typeof value.body === "string" &&
    typeof value.tags === "string" &&
    (value.pollEnabled === undefined || typeof value.pollEnabled === "boolean") &&
    (value.pollQuestion === undefined || typeof value.pollQuestion === "string") &&
    (value.pollOptions === undefined || typeof value.pollOptions === "string") &&
    (value.pollMultipleChoice === undefined || typeof value.pollMultipleChoice === "boolean") &&
    (value.pollClosesAt === undefined || typeof value.pollClosesAt === "string") &&
    (value.version === undefined || typeof value.version === "number")
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isTopicIntent(value: unknown): value is TopicIntent {
  return value === "question" || value === "bug" || value === "idea" || value === "guide";
}
</script>

<template>
  <div class="new-topic-page">
    <section class="new-topic-hero" aria-labelledby="new-topic-title">
      <div>
        <UiBadge tone="blue">发布主题</UiBadge>
        <h1 id="new-topic-title">发布一个清晰可复用的主题。</h1>
        <p>先选择合适版块，再补齐标题、日志、复现路径和标签，方便后来者继续检索和补充。</p>
      </div>
      <dl aria-label="发帖状态">
        <div>
          <dt>发布检查</dt>
          <dd>{{ completion }}/{{ checklist.length }} 项</dd>
          <small>{{ completionNote }}</small>
        </div>
        <div>
          <dt>当前版块</dt>
          <dd>{{ selectedBoard?.name }}</dd>
        </div>
        <div>
          <dt>草稿</dt>
          <dd>{{ draftStatus }}</dd>
        </div>
      </dl>
    </section>

    <div class="new-topic-layout">
      <aside class="topic-rail" aria-label="发帖步骤导航">
        <RouterLink class="rail-back" to="/boards">← 返回版块</RouterLink>
        <a v-for="link in sectionLinks" :key="link.id" class="rail-link" :href="`#${link.id}`">
          <strong>{{ link.label }}</strong>
          <span>{{ link.helper }}</span>
        </a>
      </aside>

      <form class="topic-form" aria-label="发布主题表单" @submit.prevent="handleSubmit">
        <div v-if="showConflictBanner" class="conflict-banner" role="alert">
          <span class="conflict-icon">⚠️</span>
          <span>草稿已在其他设备更新，已加载最新版本</span>
        </div>

        <UiCard id="board" class="form-panel">
          <div class="panel-heading">
            <span>01</span>
            <div>
              <h2>先选择问题归属</h2>
              <p>版块决定主题被谁看到，也决定后续如何归档。</p>
            </div>
          </div>

          <div class="board-picker" role="list" aria-label="选择版块">
            <button
              v-for="board in boardOptions"
              :key="board.id"
              type="button"
              :disabled="!board.canCreateTopic"
              :class="[
                boardToneClass(board.slug),
                { active: selectedBoardSlug === board.slug, locked: !board.canCreateTopic },
              ]"
              @click="chooseBoard(board)"
            >
              <span class="tone-mark-square" aria-hidden="true"></span>
              <strong>{{ board.name }}</strong>
              <small>{{ board.description }}</small>
              <small v-if="board.parentBoardName">子版块 · {{ board.parentBoardName }}</small>
              <small v-if="!board.canCreateTopic">仅管理员可发布主题</small>
              <em>{{ compactNumber(board.topicCount) }} 主题</em>
            </button>
          </div>
          <p v-if="boardsQuery.isError.value" class="form-error" role="alert">
            版块列表暂时不可用，发布已暂停；请稍后重试。
          </p>
          <p v-else-if="!publishableBoardOptions.length" class="form-error" role="status">
            还没有可发布的版块，请先创建版块。
          </p>
        </UiCard>

        <UiCard id="title" class="form-panel">
          <div class="panel-heading">
            <span>02</span>
            <div>
              <h2>标题先说清楚问题</h2>
              <p>推荐结构：症状 + 环境 + 关键对象，例如 “OIDC 组同步后本地手动组被移除”。</p>
            </div>
          </div>

          <div class="intent-picker" aria-label="主题类型">
            <button
              v-for="intent in topicIntents"
              :key="intent.key"
              type="button"
              :class="{ active: selectedIntent === intent.key }"
              @click="chooseIntent(intent.key)"
            >
              <strong>{{ intent.label }}</strong>
              <span>{{ intent.helper }}</span>
            </button>
          </div>

          <label class="field-block">
            <span>主题标题</span>
            <input v-model="title" maxlength="90" placeholder="例如：升级到 v0.1 后迁移提示缺少 notification_cursor 字段" />
          </label>

          <SimilarTopicHints :title="title" :body="body" :tags="parsedTags" />
        </UiCard>

        <UiCard id="content" class="form-panel">
          <div class="panel-heading">
            <span>03</span>
            <div>
              <h2>正文补齐可复现信息</h2>
              <p>把环境、步骤、日志、预期结果分开写，别人不用反复追问。</p>
            </div>
          </div>

          <div class="field-block">
            <label for="new-topic-body">正文</label>
            <textarea
              id="new-topic-body"
              ref="bodyTextarea"
              v-model="body"
              rows="10"
              placeholder="环境：\n复现步骤：\n实际结果：\n期望结果：\n我已经尝试过："
            ></textarea>
            <MarkdownUploadButton @insert="insertMarkdownUpload" />
          </div>
        </UiCard>

        <UiCard id="tags" class="form-panel">
          <div class="panel-heading">
            <span>04</span>
            <div>
              <h2>标签帮助后来者找到它</h2>
              <p>用逗号分隔，最多展示 6 个。优先写技术栈、错误对象、模块名。</p>
            </div>
          </div>

          <label class="field-block">
            <span>标签</span>
            <input v-model="tags" placeholder="例如：openid-connect, 迁移, 数据库" />
          </label>

          <div v-if="selectedBoard" class="tag-policy-box">
            <strong>版块标签策略</strong>
            <p>{{ tagPolicyHint }}</p>
            <div v-if="selectedBoard.requiredTags.length" class="tag-chip-actions">
              <button
                v-for="tag in selectedBoard.requiredTags"
                :key="tag"
                type="button"
                :disabled="parsedTags.includes(tag)"
                @click="addTag(tag)"
              >
                + #{{ tag }}
              </button>
            </div>
            <p v-if="missingRequiredTags.length" class="form-error">
              还缺少：{{ missingRequiredTags.map((tag) => `#${tag}`).join(" ") }}
            </p>
            <p v-if="disallowedTags.length" class="form-error">
              不在允许范围：{{ disallowedTags.map((tag) => `#${tag}`).join(" ") }}
            </p>
          </div>

          <div class="tag-preview" aria-label="标签预览">
            <span v-for="tag in parsedTags" :key="tag">#{{ tag }}</span>
            <em v-if="parsedTags.length === 0">还没有标签</em>
          </div>
        </UiCard>

        <UiCard id="poll" class="form-panel poll-builder">
          <div class="panel-heading">
            <span>05</span>
            <div>
              <h2>可选：附加一个 Poll</h2>
              <p>适合收集版本选择、方案偏好或复现环境。Poll 会随新主题一起创建。</p>
            </div>
          </div>

          <label class="poll-toggle">
            <input v-model="pollEnabled" type="checkbox" />
            <span>
              <strong>启用投票组件</strong>
              <small>支持单选/多选，截止后只能查看结果。</small>
            </span>
          </label>

          <div v-if="pollEnabled" class="poll-fields">
            <label class="field-block">
              <span>Poll 问题</span>
              <input v-model="pollQuestion" maxlength="140" placeholder="例如：你更希望优先支持哪种部署方式？" />
            </label>
            <label class="field-block">
              <span>选项（每行一个）</span>
              <textarea
                v-model="pollOptions"
                rows="5"
                placeholder="Docker Compose&#10;Kubernetes Helm&#10;裸机 systemd"
              ></textarea>
            </label>
            <div class="poll-settings-row">
              <label>
                <input v-model="pollMultipleChoice" type="checkbox" />
                允许多选
              </label>
              <label>
                <span>截止时间（可选）</span>
                <input v-model="pollClosesAt" type="datetime-local" />
              </label>
            </div>
            <p v-if="!pollReady" class="form-error" role="alert">
              启用 Poll 后，请填写问题并至少提供 2 个选项。
            </p>
            <div class="poll-option-preview" aria-label="Poll 选项预览">
              <span v-for="option in parsedPollOptions" :key="option">{{ option }}</span>
              <em v-if="parsedPollOptions.length === 0">每行一个选项，最多保留 12 个。</em>
            </div>
          </div>
        </UiCard>

        <UiCard id="preview" class="form-panel preview-panel">
          <div class="panel-heading">
            <span>06</span>
            <div>
              <h2>预览与发布检查</h2>
              <p>发布前先确认它是否足够清晰、可搜索、可回答。</p>
            </div>
          </div>

          <article
            v-if="selectedBoard"
            class="topic-preview-card"
            :class="boardToneClass(selectedBoard.slug)"
          >
            <header>
              <span>{{ selectedBoard?.name }}</span>
              <strong>{{ title || "这里会显示你的主题标题" }}</strong>
            </header>
            <p>{{ previewBody }}</p>
            <footer>
              <span v-for="tag in parsedTags" :key="tag">#{{ tag }}</span>
              <em v-if="parsedTags.length === 0">#待补充标签</em>
            </footer>
            <section v-if="pollEnabled" class="poll-preview-card" aria-label="Poll 预览">
              <strong>{{ pollQuestion || "这里会显示 Poll 问题" }}</strong>
              <span v-for="option in parsedPollOptions" :key="option">{{ option }}</span>
              <em v-if="parsedPollOptions.length === 0">还没有选项</em>
            </section>
          </article>

          <ul class="publish-checklist">
            <li v-for="item in checklist" :key="item.label" :class="{ done: item.done }">
              <span aria-hidden="true">{{ item.done ? "✓" : "·" }}</span>
              {{ item.label }}
            </li>
          </ul>

          <div v-if="publishState === 'submitted'" class="submit-result" role="status">
            {{ publishError || "已生成发布预览；发布成功后会跳转到新主题详情页。" }}
          </div>
        </UiCard>

        <UiCard id="drafts" class="form-panel draft-panel">
          <div>
            <h2>草稿保护</h2>
            <p>当前内容会自动保存在本机浏览器。你也可以手动保存，避免误关页面丢失。</p>
          </div>
          <div class="draft-actions">
            <UiButton type="button" tone="ghost" @click="handleSaveDraft">保存草稿</UiButton>
            <UiButton type="submit" tone="primary" :disabled="!canPublish || createTopic.isPending.value">
              {{ createTopic.isPending.value ? "发布中…" : "发布主题" }}
            </UiButton>
          </div>
        </UiCard>
      </form>

      <aside class="topic-helper" aria-label="发帖辅助说明">
        <UiCard class="helper-card">
          <span>快速模板</span>
          <h2>{{ selectedBoard?.postTemplate ? "此版块已配置模板" : "排障帖最少包含" }}</h2>
          <pre v-if="selectedBoard?.postTemplate">{{ selectedBoard.postTemplate }}</pre>
          <ol>
            <li>环境：系统、浏览器、版本、部署方式。</li>
            <li>复现：从哪个入口点到哪一步出错。</li>
            <li>日志：完整错误、请求 ID、时间点。</li>
            <li>期望：你希望它应该如何表现。</li>
          </ol>
        </UiCard>
      </aside>
    </div>
  </div>
</template>

<style scoped lang="scss" src="./NewTopicPage.scss"></style>
