<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";

import { lookupDraft } from "@/features/drafts/api";
import type { DraftResponse } from "@/features/drafts/model";
import { useDeleteDraft, useSaveDraft } from "@/features/drafts/queries";
import MarkdownUploadButton from "@/features/uploads/components/MarkdownUploadButton.vue";
import { uploadErrorMessage } from "@/features/uploads/errors";
import { toMarkdownUpload } from "@/features/uploads/model";
import { useUploadFile } from "@/features/uploads/queries";
import { getApiUrl, hasAccessToken } from "@/shared/api/client";
import { isApiErrorCode } from "@/shared/api/errors";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

import {
  buildComposerPreview,
  CODE_LANGUAGE_OPTIONS,
  COMPOSER_EMOJI_OPTIONS,
  type ComposerCodeBlock,
} from "../composerRichText";

interface ReplyDraft {
  body: string;
  version: number;
}

const props = withDefaults(
  defineProps<{
    mode?: "topic" | "reply";
    boardName?: string;
    topicTitle?: string;
    compact?: boolean;
    submitting?: boolean;
    resetToken?: number;
    draftStorageKey?: string;
  }>(),
  {
    mode: "topic",
    boardName: "支持与排障",
    topicTitle: "",
    compact: false,
    submitting: false,
    resetToken: 0,
    draftStorageKey: "",
  },
);
const emit = defineEmits<{ submit: [rawMd: string] }>();

const saveDraftMutation = useSaveDraft();
const deleteDraftMutation = useDeleteDraft();
const uploadMutation = useUploadFile();

const draft = ref("");
const title = ref("");
const tags = ref("fastapi, 排障");
const draftTextarea = ref<HTMLTextAreaElement | null>(null);
const selectedCodeLanguage = ref("ts");
const showEmojiPicker = ref(false);
const isDragActive = ref(false);
const uploadStatusMessage = ref("");
const codeCopyStatus = ref("");

const currentVersion = ref(1);
const showConflictBanner = ref(false);
const isSaving = ref(false);
let isRestoring = false;

const isReplyMode = computed(() => props.mode === "reply");
const heading = computed(() => (isReplyMode.value ? "回复这个主题" : "发一条新主题"));
const helper = computed(() =>
  isReplyMode.value
    ? "引用具体楼层、补充环境和验证结果，帮助后来者读懂脉络。"
    : "把现象、环境和你试过的方法写清楚，在线的人更容易接上。",
);
const placeholder = computed(() =>
  isReplyMode.value ? "输入回复内容" : "输入正文",
);
const composerPreview = computed(() => buildComposerPreview(draft.value));
const previewHtml = computed(() => composerPreview.value.html);
const previewFallback = computed(() =>
  isReplyMode.value ? "回复预览会显示在这里。" : "支持 Markdown、拖拽上传、链接预览和代码高亮。",
);
const previewStats = computed(() => {
  const preview = composerPreview.value;
  const parts = [`${preview.characterCount} 字符`];
  if (preview.oneboxes.length) {
    parts.push(`${preview.oneboxes.length} 个链接预览`);
  }
  if (preview.codeBlocks.length) {
    parts.push(`${preview.codeBlocks.length} 段代码`);
  }
  return parts.join(" · ");
});
const autosaveStatus = computed(() => {
  if (isSaving.value || saveDraftMutation.isPending.value) {
    return "草稿同步中…";
  }
  if (hasAccessToken() && targetId.value) {
    return `服务端草稿 v${currentVersion.value}`;
  }
  return "本地草稿已启用";
});

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

onMounted(() => {
  void initDraft();
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
  insertMarkdownBlock(markdown);
}

function insertEmoji(value: string) {
  insertMarkdownInline(value, value.length);
  showEmojiPicker.value = false;
}

function wrapSelection(prefix: string, suffix: string, fallback: string) {
  const textarea = draftTextarea.value;
  const start = textarea?.selectionStart ?? draft.value.length;
  const end = textarea?.selectionEnd ?? start;
  const selected = draft.value.slice(start, end) || fallback;
  const replacement = `${prefix}${selected}${suffix}`;
  replaceSelection(replacement, prefix.length, prefix.length + selected.length, start, end);
}

function insertLink() {
  wrapSelection("[", "](https://example.com)", "链接文字");
}

function insertQuote() {
  const selected = selectedText() || "引用文字";
  const quoted = selected
    .split("\n")
    .map((line) => `> ${line || "引用文字"}`)
    .join("\n");
  insertMarkdownBlock(quoted);
}

function insertList() {
  const selected = selectedText();
  const list = selected
    ? selected
        .split("\n")
        .filter(Boolean)
        .map((line) => `- ${line}`)
        .join("\n")
    : "- 第一项\n- 第二项";
  insertMarkdownBlock(list);
}

function insertCodeBlock() {
  const selected = selectedText() || "console.log('hello parallellines')";
  const language = selectedCodeLanguage.value || "text";
  insertMarkdownBlock(`\`\`\`${language}\n${selected}\n\`\`\``);
}

function insertMarkdownInline(markdown: string, cursorOffset = markdown.length) {
  const textarea = draftTextarea.value;
  const start = textarea?.selectionStart ?? draft.value.length;
  const end = textarea?.selectionEnd ?? start;
  replaceSelection(markdown, cursorOffset, cursorOffset, start, end);
}

function insertMarkdownBlock(markdown: string) {
  const textarea = draftTextarea.value;
  const start = textarea?.selectionStart ?? draft.value.length;
  const end = textarea?.selectionEnd ?? start;
  const before = draft.value.slice(0, start);
  const after = draft.value.slice(end);
  const leadingBreak = before && !before.endsWith("\n") ? "\n\n" : "";
  const trailingBreak = after && !after.startsWith("\n") ? "\n\n" : "";
  const insert = `${leadingBreak}${markdown}${trailingBreak}`;
  replaceSelection(insert, insert.length, insert.length, start, end);
}

function replaceSelection(markdown: string, cursorStartOffset: number, cursorEndOffset: number, start: number, end: number) {
  const textarea = draftTextarea.value;
  const before = draft.value.slice(0, start);
  const after = draft.value.slice(end);
  draft.value = `${before}${markdown}${after}`;
  const cursorStart = before.length + cursorStartOffset;
  const cursorEnd = before.length + cursorEndOffset;
  void nextTick(() => {
    textarea?.focus();
    textarea?.setSelectionRange(cursorStart, cursorEnd);
  });
}

function selectedText() {
  const textarea = draftTextarea.value;
  if (!textarea) {
    return "";
  }
  return draft.value.slice(textarea.selectionStart, textarea.selectionEnd);
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

function handlePaste(event: ClipboardEvent) {
  const files = Array.from(event.clipboardData?.files ?? []).filter((file) => file.type.startsWith("image/"));
  if (!files.length) {
    return;
  }
  event.preventDefault();
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
      insertMarkdownUpload(toMarkdownUpload(upload, getApiUrl(upload.url)));
      uploadedCount += 1;
    }
    uploadStatusMessage.value = `${uploadedCount} 个文件已上传，Markdown 引用已插入正文。`;
  } catch (error) {
    uploadStatusMessage.value = uploadErrorMessage(error);
  }
}

async function copyPreviewCode(block: ComposerCodeBlock) {
  codeCopyStatus.value = "";
  try {
    await navigator.clipboard.writeText(block.code);
    codeCopyStatus.value = `${block.language.toUpperCase()} 代码已复制。`;
  } catch {
    codeCopyStatus.value = "无法访问剪贴板，请手动复制预览代码块。";
  }
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
      <p>{{ helper }}</p>
      <span class="composer-draft-state" role="status">{{ autosaveStatus }}</span>
    </div>

    <label v-if="!isReplyMode" class="composer-field">
      <span>标题</span>
      <input v-model="title" placeholder="一句话说明问题或提案" />
    </label>

    <div class="composer-context">
      <span>{{ isReplyMode ? "回复主题" : "发布到" }}</span>
      <strong>{{ isReplyMode ? topicTitle : boardName }}</strong>
    </div>

    <section
      class="composer-editor"
      :class="{ 'composer-editor--dragging': isDragActive }"
      aria-label="Markdown 编辑器"
      @dragenter.prevent="handleDragEnter"
      @dragover.prevent="handleDragOver"
      @dragleave.prevent="handleDragLeave"
      @drop.prevent="handleDrop"
    >
      <div class="composer-toolbar" role="toolbar" aria-label="Markdown 快捷工具栏">
        <UiButton tone="ghost" type="button" @click="wrapSelection('**', '**', '重点内容')">粗体</UiButton>
        <UiButton tone="ghost" type="button" @click="wrapSelection('*', '*', '强调内容')">斜体</UiButton>
        <UiButton tone="ghost" type="button" @click="insertLink">链接</UiButton>
        <UiButton tone="ghost" type="button" @click="insertQuote">引用</UiButton>
        <UiButton tone="ghost" type="button" @click="insertList">列表</UiButton>
        <label class="composer-code-language">
          <span>代码语言</span>
          <select v-model="selectedCodeLanguage" aria-label="代码语言">
            <option v-for="language in CODE_LANGUAGE_OPTIONS" :key="language.value" :value="language.value">
              {{ language.label }}
            </option>
          </select>
        </label>
        <UiButton tone="ghost" type="button" @click="insertCodeBlock">代码块</UiButton>
        <UiButton tone="ghost" type="button" @click="showEmojiPicker = !showEmojiPicker">表情</UiButton>
      </div>

      <div v-if="showEmojiPicker" class="composer-emoji-grid" aria-label="自定义表情">
        <button
          v-for="emoji in COMPOSER_EMOJI_OPTIONS"
          :key="emoji.value"
          type="button"
          :title="emoji.description"
          @click="insertEmoji(emoji.value)"
        >
          <span>{{ emoji.preview }}</span>
          <small>{{ emoji.label }}</small>
        </button>
      </div>

      <textarea
        ref="draftTextarea"
        v-model="draft"
        :aria-label="isReplyMode ? '回复正文' : '正文'"
        :placeholder="placeholder"
        rows="6"
        @paste="handlePaste"
      />

      <div v-if="isDragActive" class="composer-drop-hint" aria-hidden="true">
        松开即可上传图片或附件，并自动插入 Markdown 引用
      </div>
    </section>

    <div class="composer-upload-row">
      <MarkdownUploadButton :compact="compact" :disabled="uploadMutation.isPending.value" @insert="insertMarkdownUpload" />
      <span v-if="uploadStatusMessage" class="composer-upload-status" role="status">{{ uploadStatusMessage }}</span>
    </div>

    <label v-if="!isReplyMode" class="composer-field composer-field--tags">
      <span>标签</span>
      <input v-model="tags" placeholder="用逗号分隔标签" />
    </label>

    <div class="composer-preview">
      <header>
        <span>实时预览</span>
        <small>{{ previewStats }}</small>
      </header>
      <div v-if="previewHtml" class="composer-preview__body" v-html="previewHtml"></div>
      <p v-else class="composer-preview__placeholder">{{ previewFallback }}</p>

      <div v-if="composerPreview.oneboxes.length" class="composer-oneboxes" aria-label="链接预览">
        <article v-for="onebox in composerPreview.oneboxes" :key="onebox.id" class="composer-onebox-card">
          <div class="composer-onebox-card__image" aria-hidden="true">{{ onebox.initial }}</div>
          <div>
            <strong>{{ onebox.title }}</strong>
            <p>{{ onebox.summary }}</p>
            <a :href="onebox.url" target="_blank" rel="noopener noreferrer">{{ onebox.host }}</a>
          </div>
        </article>
      </div>

      <div v-if="composerPreview.codeBlocks.length" class="composer-code-copy">
        <UiButton
          v-for="block in composerPreview.codeBlocks"
          :key="`${block.language}-${block.index}`"
          tone="ghost"
          type="button"
          @click="copyPreviewCode(block)"
        >
          复制 {{ block.language.toUpperCase() }} 代码
        </UiButton>
        <span v-if="codeCopyStatus" role="status">{{ codeCopyStatus }}</span>
      </div>
    </div>

    <footer>
      <UiButton tone="ghost" @click="handleSaveDraft">保存草稿</UiButton>
      <UiButton tone="primary" :disabled="!canSubmit" @click="handleSubmit">
        {{ submitting ? "发布中…" : isReplyMode ? "发布回复" : "创建主题" }}
      </UiButton>
    </footer>
  </UiCard>
</template>

<style scoped lang="scss" src="./ComposerDrawer.scss"></style>
