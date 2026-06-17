<script setup lang="ts">
import type { ExposeParam, ToolbarNames } from "md-editor-v3";
import DOMPurify from "dompurify";
import { computed, defineAsyncComponent, nextTick, onMounted, ref, watch } from "vue";

import { lookupDraft } from "@/features/drafts/api";
import type { DraftResponse } from "@/features/drafts/model";
import { useDeleteDraft, useSaveDraft } from "@/features/drafts/queries";
import MarkdownUploadButton from "@/features/uploads/components/MarkdownUploadButton.vue";
import { uploadErrorMessage } from "@/features/uploads/errors";
import { toMarkdownUpload } from "@/features/uploads/model";
import { useUploadFile } from "@/features/uploads/queries";
import { hasAccessToken, resolveApiAssetUrl } from "@/shared/api/client";
import { isApiErrorCode } from "@/shared/api/errors";
import { loadMarkdownEditorWhenIdle } from "@/shared/lib/loadMarkdownEditor";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

// Loads the heavy markdown editor and its CSS only when the composer is actually rendered.
// Key parameters: none. Return value is the async MdEditor component; side effect is downloading editor assets after idle.
const MdEditor = defineAsyncComponent(loadMarkdownEditorWhenIdle);

interface ReplyDraft {
  body: string;
  version: number;
}

type UploadImageCallback = (images: string[]) => void;

const props = withDefaults(
  defineProps<{
    mode?: "topic" | "reply";
    boardName?: string;
    topicTitle?: string;
    compact?: boolean;
    submitting?: boolean;
    resetToken?: number;
    draftStorageKey?: string;
    insertText?: string;
    insertToken?: number;
  }>(),
  {
    mode: "topic",
    boardName: "支持与排障",
    topicTitle: "",
    compact: false,
    submitting: false,
    resetToken: 0,
    draftStorageKey: "",
    insertText: "",
    insertToken: 0,
  },
);
const emit = defineEmits<{ submit: [rawMd: string] }>();

const saveDraftMutation = useSaveDraft();
const deleteDraftMutation = useDeleteDraft();
const uploadMutation = useUploadFile();

const draft = ref("");
const title = ref("");
const tags = ref("fastapi, 排障");
const composerEditorRef = ref<ExposeParam | null>(null);
const isDragActive = ref(false);
const uploadStatusMessage = ref("");

const currentVersion = ref(1);
const showConflictBanner = ref(false);
const isSaving = ref(false);
let isRestoring = false;
let lastAppliedInsertToken = 0;

const editorToolbars: ToolbarNames[] = [
  "bold",
  "italic",
  "strikeThrough",
  "quote",
  "unorderedList",
  "orderedList",
  "codeRow",
  "code",
  "link",
  "image",
  "table",
  "revoke",
  "next",
  "preview",
  "fullscreen",
];
const editorFooters: [] = [];

const isReplyMode = computed(() => props.mode === "reply");
const heading = computed(() => (isReplyMode.value ? "回复" : "发一条新主题"));
const placeholder = computed(() =>
  isReplyMode.value ? "输入回复内容" : "输入正文",
);
const canSubmit = computed(() => draft.value.trim().length > 0 && !props.submitting);

const targetId = computed(() => {
  if (props.mode === "reply" && props.draftStorageKey) {
    const prefix = "parallellines:reply-draft:";
    if (props.draftStorageKey.startsWith(prefix)) {
      return props.draftStorageKey.substring(prefix.length);
    }
  }
  return "";
});

onMounted(async () => {
  await initDraft();
  applyExternalInsert(props.insertText, props.insertToken);
});

watch(
  () => props.resetToken,
  () => {
    void clearSavedDraft();
  },
);

watch(
  () => props.draftStorageKey,
  () => {
    void initDraft();
  },
);

watch(
  () => props.insertToken,
  () => {
    applyExternalInsert(props.insertText, props.insertToken);
  },
);

watch(draft, () => {
  if (isRestoring) {
    return;
  }
  triggerAutosave();
});

function handleSubmit() {
  const rawMd = draft.value.trim();
  if (!rawMd || props.submitting) {
    return;
  }

  emit("submit", rawMd);
}

function insertMarkdownUpload(markdown: string) {
  insertDraftText(markdown);
  composerEditorRef.value?.togglePreview(true);
}

// Inserts Markdown into the current draft without depending on the editor bundle being loaded.
// Key parameter: `markdown` is appended after existing content. Side effect: mutates the local draft ref.
function insertDraftText(markdown: string) {
  const before = draft.value.trimEnd();
  draft.value = before ? `${before}\n\n${markdown}` : markdown;
}

// Applies text requested by the parent, such as quote insertion after opening the mobile composer.
// Key parameters: `markdown` is inserted once per `token`. Side effect: updates the draft and dedupe token.
function applyExternalInsert(markdown: string, token: number) {
  if (!markdown || token === lastAppliedInsertToken) {
    return;
  }

  lastAppliedInsertToken = token;
  insertDraftText(markdown);
}

function handleDragEnter(event: DragEvent) {
  if (eventHasFiles(event)) {
    isDragActive.value = true;
  }
}

function handleDragOver(event: DragEvent) {
  if (!eventHasFiles(event)) {
    return;
  }
  isDragActive.value = true;
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = "copy";
  }
}

function handleDragLeave(event: DragEvent) {
  const current = event.currentTarget;
  const related = event.relatedTarget;
  if (current instanceof Node && related instanceof Node && current.contains(related)) {
    return;
  }
  isDragActive.value = false;
}

function handleDrop(event: DragEvent) {
  isDragActive.value = false;
  const files = Array.from(event.dataTransfer?.files ?? []);
  void uploadFiles(files);
}

function eventHasFiles(event: DragEvent) {
  return Array.from(event.dataTransfer?.types ?? []).includes("Files");
}

async function uploadFiles(files: File[]) {
  const uploadableFiles = files.filter((file) => file.size > 0);
  if (!uploadableFiles.length) {
    uploadStatusMessage.value = "没有发现可上传的文件。";
    return;
  }

  uploadStatusMessage.value = `正在上传 ${uploadableFiles.length} 个文件…`;
  let uploadedCount = 0;

  try {
    for (const file of uploadableFiles) {
      const upload = await uploadMutation.mutateAsync({ file, kind: "post_attachment" });
      insertMarkdownUpload(toMarkdownUpload(upload, resolveApiAssetUrl(upload.url) ?? upload.url));
      uploadedCount += 1;
    }
    uploadStatusMessage.value = `${uploadedCount} 个文件已上传`;
  } catch (error) {
    uploadStatusMessage.value = uploadErrorMessage(error);
  }
}

/**
 * Uploads images selected from md-editor-v3 and returns absolute image URLs to its callback.
 * `files` comes from the editor image toolbar; `callback` inserts the uploaded images into the current Markdown draft.
 * Side effect: updates the upload status and reuses the authenticated post-attachment upload mutation.
 */
async function handleEditorImageUpload(files: File[], callback: UploadImageCallback) {
  const uploadableFiles = files.filter((file) => file.size > 0);
  if (!uploadableFiles.length) {
    return;
  }

  uploadStatusMessage.value = `正在上传 ${uploadableFiles.length} 个文件…`;

  try {
    const images: string[] = [];
    for (const file of uploadableFiles) {
      const upload = await uploadMutation.mutateAsync({ file, kind: "post_attachment" });
      images.push(resolveApiAssetUrl(upload.url) ?? upload.url);
    }
    callback(images);
    composerEditorRef.value?.togglePreview(true);
    uploadStatusMessage.value = "";
  } catch (error) {
    uploadStatusMessage.value = uploadErrorMessage(error);
  }
}

/**
 * Sanitizes md-editor-v3 preview HTML before it is rendered inside the editor preview pane.
 * `html` is generated from the current Markdown draft; the returned string strips unsafe markup while keeping safe link attrs.
 * Side effect: none.
 */
function sanitizeEditorHtml(html: string) {
  return DOMPurify.sanitize(html, {
    ADD_ATTR: ["target", "rel"],
  });
}

async function initDraft() {
  isRestoring = true;
  const localDraft = readSavedDraft();
  let serverDraft: DraftResponse | null = null;

  if (hasAccessToken() && targetId.value) {
    try {
      serverDraft = await lookupDraft("topic", targetId.value);
    } catch (e) {
      console.error("Failed to fetch server draft on mount/update", e);
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
    if (hasAccessToken() && targetId.value) {
      void performServerSave();
    }
  } else if (serverDraft) {
    loadDraftState(serverDraftToLocal(serverDraft));
    saveLocalDraft();
  } else {
    loadDraftState({ body: "", version: 1 });
    saveLocalDraft();
  }

  nextTick(() => {
    isRestoring = false;
  });
}

function localVerDraft(local: ReplyDraft): ReplyDraft {
  return {
    body: local.body,
    version: local.version ?? 1,
  };
}

function serverDraftToLocal(server: DraftResponse): ReplyDraft {
  return {
    body: (server.data.body as string) ?? "",
    version: server.version,
  };
}

function isDraftEqual(a: ReplyDraft, b: ReplyDraft) {
  return a.body === b.body;
}

function loadDraftState(state: ReplyDraft) {
  isRestoring = true;
  draft.value = state.body;
  currentVersion.value = state.version ?? 1;

  nextTick(() => {
    isRestoring = false;
  });
}

function saveLocalDraft() {
  if (!props.draftStorageKey || typeof window === "undefined") {
    return;
  }

  try {
    const state: ReplyDraft = {
      body: draft.value,
      version: currentVersion.value,
    };
    window.localStorage.setItem(props.draftStorageKey, JSON.stringify(state));
  } catch {
    // Ignore storage failures
  }
}

function readSavedDraft(): ReplyDraft | null {
  if (!props.draftStorageKey || typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(props.draftStorageKey);
    if (!raw) {
      return null;
    }

    if (raw.startsWith("{")) {
      const parsed = JSON.parse(raw);
      if (typeof parsed === "object" && parsed !== null) {
        return {
          body: parsed.body ?? "",
          version: parsed.version ?? 1,
        };
      }
    }

    return {
      body: raw,
      version: 1,
    };
  } catch {
    return null;
  }
}

async function clearSavedDraft() {
  isRestoring = true;
  draft.value = "";
  currentVersion.value = 1;

  if (props.draftStorageKey) {
    try {
      window.localStorage.removeItem(props.draftStorageKey);
    } catch {
      // Ignore storage failures
    }
  }

  if (hasAccessToken() && targetId.value) {
    try {
      await deleteDraftMutation.mutateAsync({ targetType: "topic", targetId: targetId.value });
    } catch (e) {
      console.error("Failed to delete server draft", e);
    }
  }

  nextTick(() => {
    isRestoring = false;
  });
}

let saveTimeout: ReturnType<typeof setTimeout> | null = null;

function triggerAutosave() {
  saveLocalDraft();

  if (!hasAccessToken() || !targetId.value) {
    return;
  }

  if (saveTimeout) {
    clearTimeout(saveTimeout);
  }

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
      body: draft.value,
    };

    const result = await saveDraftMutation.mutateAsync({
      target_type: "topic",
      target_id: targetId.value,
      draft_type: "reply",
      data: draftPayload,
      version: nextVersion,
    });

    currentVersion.value = result.version;
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
    const serverDraft = await lookupDraft("topic", targetId.value);
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
  if (hasAccessToken() && targetId.value) {
    if (saveTimeout) {
      clearTimeout(saveTimeout);
    }
    await performServerSave();
  }
}
</script>

<template>
  <UiCard class="composer" :class="{ 'composer--compact': compact, 'composer--reply': isReplyMode }">
    <div v-if="showConflictBanner" class="conflict-banner" role="alert">
      <span class="conflict-icon">⚠️</span>
      <span>草稿已在其他设备更新，已加载最新版本</span>
    </div>

    <div class="composer-heading">
      <strong>{{ heading }}</strong>
    </div>

    <label v-if="!isReplyMode" class="composer-field">
      <span>标题</span>
      <input v-model="title" placeholder="输入标题" />
    </label>

    <section
      class="composer-editor"
      :class="{ 'composer-editor--dragging': isDragActive }"
      aria-label="Markdown 编辑器"
      @dragenter.prevent="handleDragEnter"
      @dragover.prevent="handleDragOver"
      @dragleave.prevent="handleDragLeave"
      @drop.prevent="handleDrop"
    >
      <MdEditor
        ref="composerEditorRef"
        v-model="draft"
        class="composer-md-editor"
        :id="isReplyMode ? 'reply-composer-editor' : 'topic-composer-editor'"
        language="zh-CN"
        theme="light"
        preview-theme="github"
        code-theme="atom"
        :preview="false"
        :footers="editorFooters"
        :toolbars="editorToolbars"
        :sanitize="sanitizeEditorHtml"
        :transform-img-url="resolveApiAssetUrl"
        :disabled="submitting"
        :no-katex="true"
        :no-mermaid="true"
        :no-img-zoom-in="true"
        :show-code-row-number="false"
        :placeholder="placeholder"
        @onUploadImg="handleEditorImageUpload"
      />

      <div v-if="isDragActive" class="composer-drop-hint" aria-hidden="true">
        松开上传
      </div>
    </section>

    <div class="composer-upload-row">
      <MarkdownUploadButton :compact="compact" :disabled="uploadMutation.isPending.value" @insert="insertMarkdownUpload" />
      <span v-if="uploadStatusMessage" class="composer-upload-status" role="status">{{ uploadStatusMessage }}</span>
    </div>

    <label v-if="!isReplyMode" class="composer-field composer-field--tags">
      <span>标签</span>
      <input v-model="tags" placeholder="输入标签" />
    </label>

    <footer>
      <UiButton tone="ghost" @click="handleSaveDraft">保存草稿</UiButton>
      <UiButton tone="primary" :disabled="!canSubmit" @click="handleSubmit">
        {{ submitting ? "发布中…" : isReplyMode ? "发布回复" : "创建主题" }}
      </UiButton>
    </footer>
  </UiCard>
</template>

<style scoped lang="scss" src="./ComposerDrawer.scss"></style>
