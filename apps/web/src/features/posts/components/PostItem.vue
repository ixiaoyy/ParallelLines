<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import type { PostItemVM } from "@/entities/post/model";
import { setPostLike } from "@/features/interactions/api";
import { useOptimisticToggle } from "@/features/interactions/useOptimisticToggle";
import { useCreateFlag } from "@/features/moderation/queries";
import {
  useDeletePost,
  usePostRevisions,
  useRestorePostRevision,
  useUpdatePost,
} from "@/features/posts/queries";
import { hasAccessToken } from "@/shared/api/client";
import { contentPolicyMessage } from "@/shared/api/errors";
import { relativeTime } from "@/shared/lib/format";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const props = defineProps<{
  post: PostItemVM;
  currentUserId?: string | null;
  currentUserRole?: string | null;
}>();
const emit = defineEmits<{
  quote: [post: PostItemVM];
}>();

const statusMessage = ref("");
const editing = ref(false);
const editDraft = ref(props.post.rawMd);
const editReason = ref("");
const historyOpen = ref(false);
const firstCodeText = computed(() => extractFirstCodeText(props.post.cookedHtml));
const hasCodeBlock = computed(() => firstCodeText.value.length > 0);
const isOwnPost = computed(() => Boolean(props.currentUserId && props.currentUserId === props.post.userId));
const canModerateGlobally = computed(
  () => props.currentUserRole === "admin" || props.currentUserRole === "moderator",
);
const canEdit = computed(() => Boolean(isOwnPost.value && props.post.floor === 1 && !props.post.deleted));
const canDelete = computed(() => Boolean(isOwnPost.value && props.post.floor > 1 && !props.post.deleted));
const canFlag = computed(() => hasAccessToken() && !props.post.deleted);
const canViewHistory = computed(
  () => Boolean(!props.post.deleted && (isOwnPost.value || canModerateGlobally.value)),
);
const canRestoreHistory = computed(() => Boolean(!props.post.deleted && canModerateGlobally.value));
const flagPostMutation = useCreateFlag();
const flagPending = computed(() => flagPostMutation.isPending.value);
const updatePostMutation = useUpdatePost(() => props.post.topicId);
const deletePostMutation = useDeletePost(() => props.post.topicId);
const revisionsQuery = usePostRevisions(
  () => props.post.id,
  () => historyOpen.value && canViewHistory.value,
);
const restoreRevisionMutation = useRestorePostRevision(() => props.post.topicId);
const savingEdit = computed(() => updatePostMutation.isPending.value);
const deletingPost = computed(() => deletePostMutation.isPending.value);
const restoringRevision = computed(() => restoreRevisionMutation.isPending.value);
const {
  active: liked,
  count: optimisticLikeCount,
  pending: likePending,
  toggle: toggleLike,
} = useOptimisticToggle({
  active: () => false,
  count: () => props.post.likeCount,
  enabled: hasAccessToken,
  commit: (active) => setPostLike(props.post.id, active),
  readActive: (response) => response.active,
  readCount: (response) => response.count,
});

watch(
  () => props.post.rawMd,
  (rawMd) => {
    if (!editing.value) {
      editDraft.value = rawMd;
    }
  },
);

async function copyCode() {
  if (!firstCodeText.value) {
    return;
  }

  const copied = await writeClipboard(firstCodeText.value);
  setStatus(copied ? "已复制代码" : "无法访问剪贴板，已保留代码内容");
}

function quotePost() {
  emit("quote", props.post);
  setStatus("已插入引用");
}

function startEdit() {
  if (!canEdit.value) {
    return;
  }

  editDraft.value = props.post.rawMd;
  editReason.value = "";
  editing.value = true;
  statusMessage.value = "";
}

function cancelEdit() {
  editing.value = false;
  editDraft.value = props.post.rawMd;
  editReason.value = "";
}

function saveEdit() {
  const rawMd = editDraft.value.trim();
  if (!rawMd || savingEdit.value) {
    return;
  }

  updatePostMutation.mutate(
    {
      postId: props.post.id,
      payload: { raw_md: rawMd, edit_reason: editReason.value.trim() || null },
    },
    {
      onSuccess: () => {
        editing.value = false;
        editReason.value = "";
        setStatus("已保存编辑");
      },
      onError: (error) => {
        setStatus(contentPolicyMessage(error, "保存失败，请确认登录状态后重试"));
      },
    },
  );
}

function toggleHistory() {
  if (!canViewHistory.value) {
    return;
  }

  historyOpen.value = !historyOpen.value;
  if (historyOpen.value) {
    void revisionsQuery.refetch();
  }
}

function restoreRevision(revisionId: string, versionNumber: number) {
  if (!canRestoreHistory.value || restoringRevision.value) {
    return;
  }

  restoreRevisionMutation.mutate(
    {
      postId: props.post.id,
      revisionId,
      payload: { reason: `恢复到版本 ${versionNumber}` },
    },
    {
      onSuccess: () => {
        setStatus(`已恢复到版本 ${versionNumber}`);
      },
      onError: () => {
        setStatus("恢复失败，请确认版主权限后重试");
      },
    },
  );
}

function deleteReply() {
  if (!canDelete.value || deletingPost.value) {
    return;
  }

  const confirmed = window.confirm("确定删除这条回复吗？删除后正文会被隐藏。");
  if (!confirmed) {
    return;
  }

  deletePostMutation.mutate(props.post.id, {
    onSuccess: () => setStatus("回复已删除"),
    onError: () => setStatus("删除失败，请确认登录状态后重试"),
  });
}

function flagPost() {
  if (!canFlag.value) {
    return;
  }

  flagPostMutation.mutate({
    target_type: "post",
    target_id: props.post.id,
    reason: "other",
    detail: "用户从楼层操作发起举报。",
  });
}

function extractFirstCodeText(html: string) {
  if (!html.includes("<pre")) {
    return "";
  }

  const template = document.createElement("template");
  template.innerHTML = html;
  return template.content.querySelector("pre code, pre")?.textContent?.trim() ?? "";
}

async function writeClipboard(value: string) {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

function setStatus(message: string) {
  statusMessage.value = message;
  void nextTick(() => {
    window.setTimeout(() => {
      if (statusMessage.value === message) {
        statusMessage.value = "";
      }
    }, 2400);
  });
}
</script>

<template>
  <UiCard class="post-item" :class="{ deleted: post.deleted }">
    <aside class="post-author">
      <UiAvatar :name="post.authorName" />
      <strong>{{ post.authorName }}</strong>
      <span>#{{ post.floor }}</span>
    </aside>
    <article class="post-body">
      <time>{{ relativeTime(post.createdAt) }}</time>
      <div v-if="post.deleted" class="deleted-copy">该楼层已删除或隐藏。</div>
      <template v-else-if="editing">
        <label class="edit-field">
          <span>编辑本楼层</span>
          <textarea v-model="editDraft" rows="6" aria-label="编辑回复内容" />
        </label>
        <label class="edit-field edit-field--compact">
          <span>编辑原因（可选）</span>
          <input v-model="editReason" maxlength="500" placeholder="例如：补充复现步骤、修正错别字" />
        </label>
        <div class="edit-actions">
          <UiButton tone="primary" :disabled="!editDraft.trim() || savingEdit" @click="saveEdit">
            {{ savingEdit ? "保存中…" : "保存编辑" }}
          </UiButton>
          <UiButton tone="ghost" :disabled="savingEdit" @click="cancelEdit">取消编辑</UiButton>
        </div>
      </template>
      <div v-else class="markdown-body" v-html="post.cookedHtml" />
      <p v-if="statusMessage" class="post-status" role="status">{{ statusMessage }}</p>
      <footer v-if="!post.deleted">
        <UiButton
          :tone="liked ? 'success' : 'ghost'"
          :aria-pressed="liked"
          :disabled="likePending"
          @click="toggleLike"
        >
          {{ liked ? "已赞" : "赞" }} {{ optimisticLikeCount }}
        </UiButton>
        <UiButton tone="ghost" @click="quotePost">回复 {{ post.replyCount }}</UiButton>
        <UiButton v-if="hasCodeBlock" tone="subtle" aria-label="复制本楼层代码块" @click="copyCode">复制代码</UiButton>
        <UiButton tone="ghost" :disabled="flagPending || !canFlag" @click="flagPost">举报</UiButton>
        <UiButton tone="ghost" @click="quotePost">引用</UiButton>
        <UiButton v-if="canEdit" tone="subtle" @click="startEdit">编辑</UiButton>
        <UiButton v-if="canViewHistory" tone="ghost" @click="toggleHistory">
          {{ historyOpen ? "收起历史" : "历史" }}
        </UiButton>
        <UiButton v-if="canDelete" class="post-delete-button" tone="ghost" :disabled="deletingPost" @click="deleteReply">
          {{ deletingPost ? "删除中…" : "删除" }}
        </UiButton>
      </footer>
      <section v-if="historyOpen && canViewHistory" class="revision-panel" aria-label="帖子编辑历史">
        <p v-if="revisionsQuery.isLoading.value" role="status">正在加载编辑历史…</p>
        <p v-else-if="revisionsQuery.isError.value" role="alert">编辑历史加载失败。</p>
        <p v-else-if="!revisionsQuery.data.value?.length">暂无历史版本。</p>
        <template v-else>
          <article v-for="revision in revisionsQuery.data.value" :key="revision.id" class="revision-card">
            <header>
              <strong>版本 {{ revision.versionNumber }}</strong>
              <span>{{ revision.editorName ?? "已删除用户" }} · {{ relativeTime(revision.createdAt) }}</span>
            </header>
            <p>{{ revision.summary }}</p>
            <pre>{{ revision.rawMd.slice(0, 260) }}{{ revision.rawMd.length > 260 ? "…" : "" }}</pre>
            <UiButton
              v-if="canRestoreHistory"
              tone="subtle"
              :disabled="restoringRevision"
              @click="restoreRevision(revision.id, revision.versionNumber)"
            >
              恢复此版本
            </UiButton>
          </article>
        </template>
      </section>
    </article>
  </UiCard>
</template>

<style scoped lang="scss" src="./PostItem.scss"></style>
