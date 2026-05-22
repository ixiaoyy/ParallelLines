<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";

import { lookupDraft } from "@/features/drafts/api";
import { useSaveDraft, useDeleteDraft } from "@/features/drafts/queries";
import type { DraftResponse } from "@/features/drafts/model";
import MarkdownUploadButton from "@/features/uploads/components/MarkdownUploadButton.vue";
import { hasAccessToken } from "@/shared/api/client";
import { isApiErrorCode } from "@/shared/api/errors";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

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

const draft = ref("");
const title = ref("");
const tags = ref("fastapi, 排障");
const draftTextarea = ref<HTMLTextAreaElement | null>(null);

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
  isReplyMode.value
    ? "例如：我在 PostgreSQL 15 下复现了，同样会卡在任务状态刷新…"
    : "例如：升级后登录会跳回首页，只有 Edge 复现…",
);
const previewText = computed(() =>
  draft.value.trim() || (isReplyMode.value ? "回复预览会显示在这里。" : "环境：Windows 11 / Edge 126 / 单点登录开启"),
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
  const textarea = draftTextarea.value;
  if (!textarea) {
    draft.value = [draft.value.trimEnd(), markdown].filter(Boolean).join("\n\n");
    return;
  }

  const start = textarea.selectionStart ?? draft.value.length;
  const end = textarea.selectionEnd ?? start;
  const before = draft.value.slice(0, start);
  const after = draft.value.slice(end);
  const leadingBreak = before && !before.endsWith("\n") ? "\n\n" : "";
  const trailingBreak = after && !after.startsWith("\n") ? "\n\n" : "";
  const insert = `${leadingBreak}${markdown}${trailingBreak}`;
  draft.value = `${before}${insert}${after}`;
  const cursor = before.length + insert.length;
  void nextTick(() => {
    textarea.focus();
    textarea.setSelectionRange(cursor, cursor);
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
      <p>{{ helper }}</p>
    </div>

    <label v-if="!isReplyMode" class="composer-field">
      <span>标题</span>
      <input v-model="title" placeholder="一句话说明问题或提案" />
    </label>

    <div class="composer-context">
      <span>{{ isReplyMode ? "回复主题" : "发布到" }}</span>
      <strong>{{ isReplyMode ? topicTitle : boardName }}</strong>
    </div>

    <textarea
      ref="draftTextarea"
      v-model="draft"
      :aria-label="isReplyMode ? '回复正文' : '正文'"
      :placeholder="placeholder"
      rows="4"
    />
    <MarkdownUploadButton :compact="compact" @insert="insertMarkdownUpload" />

    <label v-if="!isReplyMode" class="composer-field composer-field--tags">
      <span>标签</span>
      <input v-model="tags" placeholder="用逗号分隔标签" />
    </label>

    <div class="composer-preview">
      <span>草稿预览</span>
      <p>{{ previewText }}</p>
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
