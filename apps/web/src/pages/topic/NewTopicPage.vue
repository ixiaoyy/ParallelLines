<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import type { BoardSummary } from "@/entities/board/model";
import { useBoards } from "@/features/boards/queries";
import { lookupDraft } from "@/features/drafts/api";
import type { DraftResponse } from "@/features/drafts/model";
import { useDeleteDraft, useSaveDraft } from "@/features/drafts/queries";
import { useCreateTopic } from "@/features/topics/queries";
import MarkdownUploadButton from "@/features/uploads/components/MarkdownUploadButton.vue";
import { contentPolicyMessage, isApiErrorCode } from "@/shared/api/errors";
import { ApiError, hasAccessToken } from "@/shared/api/client";
import { readRouteParam } from "@/shared/router/params";
import { topicDetailRoute } from "@/shared/router/topicRoutes";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

interface NewTopicDraft {
  boardSlug: string;
  title: string;
  body: string;
  tags: string;
  version: number;
}

type PublishState = "idle" | "saved" | "submitted";

const DRAFT_STORAGE_KEY = "parallellines:new-topic-draft";

const route = useRoute();
const router = useRouter();
const boardsQuery = useBoards();
const createTopic = useCreateTopic();
const saveDraftMutation = useSaveDraft();
const deleteDraftMutation = useDeleteDraft();

const selectedBoardSlug = ref("support");
const title = ref("");
const body = ref("");
const tags = ref("");
const currentVersion = ref(1);

const bodyTextarea = ref<HTMLTextAreaElement | null>(null);
const publishState = ref<PublishState>("idle");
const publishError = ref("");
const showConflictBanner = ref(false);
const isSaving = ref(false);

const boardOptions = computed(() => boardsQuery.data.value ?? []);
const publishableBoardOptions = computed(() => boardOptions.value.filter((board) => board.canCreateTopic));
const selectedBoard = computed(
  () => boardOptions.value.find((board) => board.slug === selectedBoardSlug.value) ?? publishableBoardOptions.value[0],
);
const selectedBoardCanCreateTopic = computed(() => Boolean(selectedBoard.value?.canCreateTopic));

const parsedTags = computed(() =>
  tags.value
    .split(/[，,]/)
    .map((tag) => tag.trim())
    .filter(Boolean)
    .slice(0, 8),
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
const suggestedTags = computed(() => {
  const board = selectedBoard.value;
  if (!board) {
    return [];
  }

  return [...new Set([...board.requiredTags, ...board.allowedTags])]
    .filter((tag) => !parsedTags.value.includes(tag))
    .slice(0, 8);
});
const tagIssue = computed(() => {
  if (missingRequiredTags.value.length) {
    return `需要：${missingRequiredTags.value.map((tag) => `#${tag}`).join(" ")}`;
  }

  if (disallowedTags.value.length) {
    return `不可用：${disallowedTags.value.map((tag) => `#${tag}`).join(" ")}`;
  }

  return "";
});
const draftStatus = computed(() => {
  if (isSaving.value) {
    return "保存中";
  }

  if (publishState.value === "saved") {
    return "草稿已保存";
  }

  return "正在编辑";
});
const canPublish = computed(() => validationMessage() === "");

let isRestoring = false;
let saveTimeout: ReturnType<typeof setTimeout> | null = null;

watch(
  selectedBoard,
  (board) => {
    if (!board || isRestoring) {
      return;
    }

    ensureRequiredTags(board);
    if (!body.value.trim() && board.postTemplate) {
      body.value = board.postTemplate;
    }
  },
  { immediate: true },
);

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

watch([selectedBoardSlug, title, body, tags], () => {
  if (isRestoring) {
    return;
  }

  publishError.value = "";
  triggerAutosave();
});

onMounted(async () => {
  isRestoring = true;
  const localDraft = readSavedDraft();
  let serverDraft: DraftResponse | null = null;

  if (hasAccessToken()) {
    try {
      serverDraft = await lookupDraft("new_topic", "");
    } catch {
      serverDraft = null;
    }
  }

  if (localDraft && serverDraft) {
    const localVersion = localDraft.version ?? 1;
    if (localVersion >= serverDraft.version) {
      loadDraftState(localVerDraft(localDraft));
      if (localVersion > serverDraft.version) {
        void performServerSave();
      }
    } else {
      loadDraftState(serverDraftToLocal(serverDraft));
      saveLocalDraft();
    }
  } else if (localDraft) {
    loadDraftState(localVerDraft(localDraft));
    if (hasAccessToken()) {
      void performServerSave();
    }
  } else if (serverDraft) {
    loadDraftState(serverDraftToLocal(serverDraft));
    saveLocalDraft();
  }

  nextTick(() => {
    isRestoring = false;
    if (selectedBoard.value) {
      ensureRequiredTags(selectedBoard.value);
    }
  });
});

function addTag(tag: string) {
  const currentTags = parsedTags.value;
  if (currentTags.includes(tag)) {
    return;
  }

  tags.value = [...currentTags, tag].join(", ");
}

function removeTag(tag: string) {
  tags.value = parsedTags.value.filter((current) => current !== tag).join(", ");
}

function ensureRequiredTags(board: BoardSummary) {
  if (!board.requiredTags.length) {
    return;
  }

  const nextTags = [...new Set([...parsedTags.value, ...board.requiredTags])];
  if (nextTags.length !== parsedTags.value.length) {
    tags.value = nextTags.join(", ");
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
  const validation = validationMessage();
  if (validation) {
    publishError.value = validation;
    publishState.value = "submitted";
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
        poll: null,
      },
    });

    if (hasAccessToken()) {
      try {
        await deleteDraftMutation.mutateAsync({ targetType: "new_topic", targetId: "" });
      } catch {
        // Keep navigation fast; stale drafts are safe to overwrite on the next edit.
      }
    }
    window.localStorage.removeItem(DRAFT_STORAGE_KEY);
    await router.push(topicDetailRoute(topic));
  } catch (error) {
    publishState.value = "submitted";
    publishError.value =
      boardPolicyMessage(error) ?? contentPolicyMessage(error, "未登录或服务暂时不可用，内容已保留。");
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

function validationMessage(): string {
  if (boardsQuery.isError.value) {
    return "版块列表不可用，请稍后再试。";
  }

  if (!selectedBoard.value) {
    return "请选择版块。";
  }

  if (!selectedBoardCanCreateTopic.value) {
    return "该版块暂不允许你发布主题。";
  }

  if (title.value.trim().length < 4) {
    return "标题至少 4 个字。";
  }

  if (!body.value.trim()) {
    return "正文不能为空。";
  }

  if (missingRequiredTags.value.length) {
    return `请补齐标签：${missingRequiredTags.value.map((tag) => `#${tag}`).join(" ")}`;
  }

  if (disallowedTags.value.length) {
    return `这些标签不可用：${disallowedTags.value.map((tag) => `#${tag}`).join(" ")}`;
  }

  return "";
}

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
    if (saveTimeout) {
      clearTimeout(saveTimeout);
    }
    saveTimeout = setTimeout(performServerSave, 500);
    return;
  }

  isSaving.value = true;
  const nextVersion = currentVersion.value + 1;

  try {
    const result = await saveDraftMutation.mutateAsync({
      target_type: "new_topic",
      target_id: "",
      draft_type: "topic",
      data: {
        boardSlug: selectedBoardSlug.value,
        title: title.value,
        body: body.value,
        tags: tags.value,
      },
      version: nextVersion,
    });

    currentVersion.value = result.version;
    publishState.value = "saved";
    saveLocalDraft();
  } catch (error: unknown) {
    if (isApiErrorCode(error, "draft_conflict")) {
      await handleDraftConflict();
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
  } catch {
    // If recovery fails, keep the local draft visible so the user can still publish or copy it.
  }
}

function boardPolicyMessage(error: unknown): string | null {
  if (error instanceof ApiError && error.code === "required_tags_missing") {
    const missing = Array.isArray(error.details.missing_tags)
      ? error.details.missing_tags.join("、")
      : "必填标签";
    return `请补齐标签：${missing}`;
  }

  if (error instanceof ApiError && error.code === "tag_not_allowed") {
    const disallowed = Array.isArray(error.details.disallowed_tags)
      ? error.details.disallowed_tags.join("、")
      : "不允许的标签";
    return `这些标签不可用：${disallowed}`;
  }

  if (error instanceof ApiError && error.code === "board_topic_create_restricted") {
    return "该版块暂不允许你发布主题。";
  }

  return null;
}

function localVerDraft(local: NewTopicDraft): NewTopicDraft {
  return {
    boardSlug: local.boardSlug,
    title: local.title,
    body: local.body,
    tags: local.tags,
    version: local.version ?? 1,
  };
}

function serverDraftToLocal(server: DraftResponse): NewTopicDraft {
  return {
    boardSlug: (server.data.boardSlug as string) ?? "support",
    title: (server.data.title as string) ?? "",
    body: (server.data.body as string) ?? "",
    tags: (server.data.tags as string) ?? "",
    version: server.version,
  };
}

function loadDraftState(draft: NewTopicDraft) {
  isRestoring = true;
  selectedBoardSlug.value = draft.boardSlug;
  title.value = draft.title;
  body.value = draft.body;
  tags.value = draft.tags;
  currentVersion.value = draft.version ?? 1;

  nextTick(() => {
    isRestoring = false;
  });
}

function saveLocalDraft() {
  if (typeof window === "undefined") {
    return;
  }

  const draft: NewTopicDraft = {
    boardSlug: selectedBoardSlug.value,
    title: title.value,
    body: body.value,
    tags: tags.value,
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
    return isDraft(value) ? value : null;
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
    typeof value.title === "string" &&
    typeof value.body === "string" &&
    typeof value.tags === "string" &&
    (value.version === undefined || typeof value.version === "number")
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
</script>

<template>
  <div class="new-topic-page">
    <form class="topic-composer" aria-label="创建新话题" @submit.prevent="handleSubmit">
      <UiCard class="composer-card">
        <header class="composer-heading">
          <span class="composer-plus" aria-hidden="true">＋</span>
          <div>
            <h1>创建新话题</h1>
            <p>{{ draftStatus }}</p>
          </div>
        </header>

        <div v-if="showConflictBanner" class="conflict-banner" role="alert">
          草稿已在其他设备更新，已加载最新版本。
        </div>

        <label class="title-field">
          <span class="sr-only">标题</span>
          <input
            v-model="title"
            maxlength="180"
            placeholder="输入标题，或在此处粘贴链接"
            autocomplete="off"
          />
          <em>{{ title.trim().length }}/4</em>
        </label>

        <div class="composer-meta-row">
          <label class="select-field">
            <span class="sr-only">版块</span>
            <select v-model="selectedBoardSlug" :disabled="boardsQuery.isLoading.value">
              <option v-if="boardsQuery.isLoading.value" value="">正在加载版块…</option>
              <option
                v-for="board in boardOptions"
                :key="board.id"
                :value="board.slug"
                :disabled="!board.canCreateTopic"
              >
                {{ board.parentBoardName ? `${board.parentBoardName} / ` : "" }}{{ board.name }}{{ board.canCreateTopic ? "" : "（不可发布）" }}
              </option>
            </select>
          </label>

          <label class="tag-field">
            <span class="sr-only">标签</span>
            <input v-model="tags" placeholder="可选标签，用逗号分隔" />
          </label>
        </div>

        <div v-if="suggestedTags.length || parsedTags.length || tagIssue" class="tag-strip" aria-label="标签">
          <button
            v-for="tag in suggestedTags"
            :key="tag"
            type="button"
            class="tag-suggestion"
            @click="addTag(tag)"
          >
            + #{{ tag }}
          </button>
          <button
            v-for="tag in parsedTags"
            :key="`selected-${tag}`"
            type="button"
            class="tag-chip"
            @click="removeTag(tag)"
          >
            #{{ tag }} ×
          </button>
          <span v-if="tagIssue" class="tag-issue">{{ tagIssue }}</span>
        </div>

        <div class="editor-box">
          <div class="editor-toolbar">
            <MarkdownUploadButton compact @insert="insertMarkdownUpload" />
            <span>Markdown</span>
          </div>
          <textarea
            ref="bodyTextarea"
            v-model="body"
            rows="16"
            maxlength="20000"
            placeholder="在此处输入。可拖放或上传图片。"
          ></textarea>
          <span class="body-count">{{ body.length }}/20000</span>
        </div>

        <p v-if="publishError" class="form-error" role="alert">{{ publishError }}</p>

        <footer class="composer-footer">
          <RouterLink class="discard-link" to="/boards">舍弃</RouterLink>
          <UiButton type="button" tone="ghost" @click="handleSaveDraft">保存草稿</UiButton>
          <UiButton type="submit" tone="primary" :disabled="createTopic.isPending.value || boardsQuery.isLoading.value">
            {{ createTopic.isPending.value ? "发布中…" : canPublish ? "创建话题" : "创建话题" }}
          </UiButton>
        </footer>
      </UiCard>
    </form>
  </div>
</template>

<style scoped lang="scss" src="./NewTopicPage.scss"></style>
