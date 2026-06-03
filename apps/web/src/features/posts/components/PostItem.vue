<script setup lang="ts">
import {
  CheckCircleOutlined,
  CodeOutlined,
  DeleteOutlined,
  EditOutlined,
  EllipsisOutlined,
  FlagOutlined,
  HeartFilled,
  HeartOutlined,
  HistoryOutlined,
  LinkOutlined,
  RocketOutlined,
  RollbackOutlined,
  UserDeleteOutlined,
} from "@ant-design/icons-vue";
import type { ExposeParam, ToolbarNames } from "md-editor-v3";
import DOMPurify from "dompurify";
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import type { PostItemVM } from "@/entities/post/model";
import { setPostLike } from "@/features/interactions/api";
import { useOptimisticToggle } from "@/features/interactions/useOptimisticToggle";
import ReportModal from "@/features/moderation/components/ReportModal.vue";
import {
  useDeletePost,
  usePostRevisions,
  useRestorePostRevision,
  useUpdatePost,
} from "@/features/posts/queries";
import MarkdownUploadButton from "@/features/uploads/components/MarkdownUploadButton.vue";
import { uploadErrorMessage } from "@/features/uploads/errors";
import { useUploadFile } from "@/features/uploads/queries";
import { hasAccessToken, resolveApiAssetUrl } from "@/shared/api/client";
import { contentPolicyMessage } from "@/shared/api/errors";
import { relativeTime } from "@/shared/lib/format";
import { runWhenBrowserIdle } from "@/shared/lib/loadWhenIdle";
import { useOutsidePointerDown } from "@/shared/lib/useOutsidePointerDown";
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const MdEditor = defineAsyncComponent(() =>
  runWhenBrowserIdle().then(() => import("md-editor-v3").then((module) => module.MdEditor)),
);

interface ComicPage {
  src: string;
  alt: string;
}

const props = withDefaults(defineProps<{
  post: PostItemVM;
  currentUserId?: string | null;
  currentUserRole?: string | null;
  canManageSolution?: boolean;
  solutionPending?: boolean;
  comicReader?: boolean;
  variant?: "article" | "reply";
}>(), {
  comicReader: false,
  variant: "reply",
});
const emit = defineEmits<{
  blockAuthor: [post: PostItemVM];
  quote: [post: PostItemVM];
  requireLogin: [message: string];
  toggleSolution: [post: PostItemVM];
}>();

const statusMessage = ref("");
const editing = ref(false);
const editDraft = ref(props.post.rawMd);
const editEditorRef = ref<ExposeParam | null>(null);
const historyOpen = ref(false);
const reportModalOpen = ref(false);
const bodyRef = ref<HTMLElement | null>(null);
const postMoreRef = ref<HTMLDetailsElement | null>(null);
const activeComicPageIndex = ref(0);
const prefetchedComicImageUrls = new Set<string>();
let nextComicPreloadTimer: number | null = null;
const firstCodeText = computed(() => extractFirstCodeText(props.post.cookedHtml));
const hasCodeBlock = computed(() => firstCodeText.value.length > 0);
const isOwnPost = computed(() => Boolean(props.currentUserId && props.currentUserId === props.post.userId));
const canModerateGlobally = computed(
  () => props.currentUserRole === "admin" || props.currentUserRole === "moderator",
);
const canEdit = computed(() => Boolean(isOwnPost.value && props.post.floor === 1 && !props.post.deleted));
const canDelete = computed(() =>
  Boolean(!props.post.deleted && props.post.floor > 1 && (isOwnPost.value || canModerateGlobally.value)),
);
const canFlag = computed(() => hasAccessToken() && !props.post.deleted);
const canBlockAuthor = computed(() => Boolean(!props.post.deleted && !isOwnPost.value));
const canToggleSolution = computed(
  () => Boolean(props.canManageSolution && props.post.floor > 1 && !props.post.deleted),
);
const authorRoleBadge = computed(() => roleBadgeLabel(props.post.authorRole));
const editedAfterPublish = computed(() => isEditedAfterPublish(props.post.createdAt, props.post.updatedAt));
const canViewHistory = computed(
  () => Boolean(!props.post.deleted && (isOwnPost.value || canModerateGlobally.value)),
);
const canRestoreHistory = computed(() => Boolean(!props.post.deleted && canModerateGlobally.value));
const renderedPostHtml = computed(() => withResolvedImageHtml(props.post.cookedHtml, props.comicReader));
const comicPages = computed(() => (props.comicReader ? extractComicPages(props.post.cookedHtml) : []));
const hasComicPages = computed(() => props.comicReader && comicPages.value.length > 0);
const activeComicPage = computed(() => comicPages.value[activeComicPageIndex.value] ?? null);
const updatePostMutation = useUpdatePost(() => props.post.topicId);
const deletePostMutation = useDeletePost(() => props.post.topicId);
const uploadMutation = useUploadFile();
const revisionsQuery = usePostRevisions(
  () => props.post.id,
  () => historyOpen.value && canViewHistory.value,
);
const restoreRevisionMutation = useRestorePostRevision(() => props.post.topicId);
const savingEdit = computed(() => updatePostMutation.isPending.value);
const deletingPost = computed(() => deletePostMutation.isPending.value);
const restoringRevision = computed(() => restoreRevisionMutation.isPending.value);
const editEditorToolbars: ToolbarNames[] = [
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
const editEditorFooters: [] = [];

type UploadImageCallback = (images: string[]) => void;
const {
  active: liked,
  count: optimisticLikeCount,
  pending: likePending,
  toggle: toggleLike,
} = useOptimisticToggle({
  active: () => Boolean(props.post.likedByMe),
  count: () => props.post.likeCount,
  enabled: hasAccessToken,
  commit: (active) => setPostLike(props.post.id, active),
  readActive: (response) => response.active,
  readCount: (response) => response.count,
  onDisabled: () => requestLogin("请先登录后再点赞楼层。"),
  mockWhenDisabled: false,
});

watch(
  () => props.post.rawMd,
  (rawMd) => {
    if (!editing.value) {
      editDraft.value = rawMd;
    }
  },
);

// Purpose: keeps the active comic page valid when rendered Markdown images change.
// Key parameters: `pages` is the extracted page list. Return value: none; side effect: may reset active page and schedule preload.
watch(
  comicPages,
  (pages) => {
    if (activeComicPageIndex.value >= pages.length) {
      activeComicPageIndex.value = Math.max(0, pages.length - 1);
    }
    scheduleNextComicPagePreload();
  },
  { immediate: true },
);

// Purpose: starts the next-page background preload only after the visible comic page changes.
// Key parameters: none. Return value: none; side effect: may schedule a delayed low-priority image request.
watch(activeComicPageIndex, () => {
  scheduleNextComicPagePreload();
});

// Purpose: prevents delayed comic preloads from firing after this post item is destroyed.
// Key parameters: none. Return value: none; side effect: clears any pending preload timer.
onBeforeUnmount(() => {
  if (nextComicPreloadTimer !== null) {
    window.clearTimeout(nextComicPreloadTimer);
    nextComicPreloadTimer = null;
  }
});

watch(
  () => [props.post.cookedHtml, props.comicReader] as const,
  () => {
    void nextTick(decorateRenderedContent);
  },
  { immediate: true },
);

onMounted(() => {
  decorateRenderedContent();
});

useOutsidePointerDown(postMoreRef, closeMoreMenu, () => Boolean(postMoreRef.value?.open));

async function copyCode() {
  if (!firstCodeText.value) {
    return;
  }

  closeMoreMenu();
  const copied = await writeClipboard(firstCodeText.value);
  setStatus(copied ? "已复制代码" : "无法访问剪贴板，已保留代码内容");
}

function quotePost() {
  emit("quote", props.post);
  setStatus("已插入引用");
}

function toggleSolution() {
  if (!canToggleSolution.value || props.solutionPending) {
    return;
  }
  emit("toggleSolution", props.post);
}

function startEdit() {
  if (!canEdit.value) {
    return;
  }

  editDraft.value = props.post.rawMd;
  editing.value = true;
  statusMessage.value = "";
}

function cancelEdit() {
  editing.value = false;
  editDraft.value = props.post.rawMd;
}

/**
 * Appends Markdown emitted by the attachment upload button into the edit draft.
 * `markdown` is the already-formatted image/file link; side effect: enables editor preview so uploads are visible immediately.
 */
function insertEditMarkdownUpload(markdown: string) {
  const before = editDraft.value.trimEnd();
  editDraft.value = before ? `${before}\n\n${markdown}` : markdown;
  editEditorRef.value?.togglePreview(true);
}

/**
 * Uploads images selected from the edit editor toolbar and hands absolute image URLs back to md-editor-v3.
 * `files` comes from the editor image picker; side effect: updates the visible edit status message.
 */
async function handleEditImageUpload(files: File[], callback: UploadImageCallback) {
  const uploadableFiles = files.filter((file) => file.size > 0);
  if (!uploadableFiles.length) {
    return;
  }

  statusMessage.value = `正在上传 ${uploadableFiles.length} 个文件…`;

  try {
    const images: string[] = [];
    for (const file of uploadableFiles) {
      const upload = await uploadMutation.mutateAsync({ file, kind: "post_attachment" });
      images.push(resolveApiAssetUrl(upload.url) ?? upload.url);
    }
    callback(images);
    editEditorRef.value?.togglePreview(true);
    setStatus("图片已上传");
  } catch (error) {
    setStatus(uploadErrorMessage(error));
  }
}

/**
 * Sanitizes the edit editor preview HTML before rendering.
 * `html` is md-editor-v3 preview output; return value strips unsafe markup without mutating the draft.
 */
function sanitizeEditHtml(html: string) {
  return DOMPurify.sanitize(html, {
    ADD_ATTR: ["target", "rel"],
  });
}

function saveEdit() {
  const rawMd = editDraft.value.trim();
  if (!rawMd || savingEdit.value) {
    return;
  }

  updatePostMutation.mutate(
    {
      postId: props.post.id,
      payload: { raw_md: rawMd },
    },
    {
      onSuccess: () => {
        editing.value = false;
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

  closeMoreMenu();
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

  closeMoreMenu();
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
  closeMoreMenu();
  reportModalOpen.value = true;
}

function blockAuthor() {
  if (!canBlockAuthor.value) {
    return;
  }
  closeMoreMenu();
  emit("blockAuthor", props.post);
}

async function copyPostLink() {
  const fallbackUrl = `${window.location.href.split("#")[0]}#post-${props.post.floor}`;
  const url = props.post.shareUrl
    ? new URL(props.post.shareUrl, window.location.origin).href
    : fallbackUrl;
  const copied = await writeClipboard(url);
  if (!copied) {
    window.location.hash = `post-${props.post.floor}`;
  }
  setStatus(copied ? "已复制楼层链接" : "无法访问剪贴板，已更新地址栏锚点");
}

function requestLogin(message: string) {
  setStatus(message);
  emit("requireLogin", message);
}

function roleBadgeLabel(role: string) {
  const labels: Record<string, string> = {
    admin: "管理员",
    moderator: "版主",
  };
  return labels[role] ?? "";
}

function isEditedAfterPublish(createdAt: string, updatedAt: string) {
  const created = Date.parse(createdAt);
  const updated = Date.parse(updatedAt);
  if (Number.isNaN(created) || Number.isNaN(updated)) {
    return createdAt !== updatedAt;
  }
  return updated - created > 1000;
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

function closeMoreMenu() {
  if (postMoreRef.value) {
    postMoreRef.value.open = false;
  }
}

/**
 * Resolves rendered Markdown image sources before `v-html` inserts them into the DOM.
 * Key parameters: `html` is backend-rendered Markdown and `prioritizeFirstImage` controls the first image load priority.
 * Return value: HTML with absolute image URLs plus loading/decoding/fetchpriority attributes; side effect: none.
 */
function withResolvedImageHtml(html: string, prioritizeFirstImage: boolean) {
  const template = document.createElement("template");
  template.innerHTML = html;

  template.content.querySelectorAll<HTMLImageElement>("img").forEach((image, index) => {
    const originalSource = image.getAttribute("src")?.trim();
    const resolvedSource = resolveApiAssetUrl(originalSource) ?? originalSource;
    if (resolvedSource) {
      image.setAttribute("src", resolvedSource);
    }

    image.loading = prioritizeFirstImage && index === 0 ? "eager" : "lazy";
    image.decoding = "async";
    image.setAttribute("fetchpriority", prioritizeFirstImage && index === 0 ? "high" : "low");
  });

  return template.innerHTML;
}

/**
 * Extracts ordered comic page images from rendered Markdown for the dedicated reader.
 * Key parameter: `html` is backend-rendered Markdown. Return value: image page metadata with API-absolute URLs.
 * Side effect: none.
 */
function extractComicPages(html: string): ComicPage[] {
  const template = document.createElement("template");
  template.innerHTML = html;

  return Array.from(template.content.querySelectorAll<HTMLImageElement>("img"))
    .map((image, index) => {
      const originalSource = image.getAttribute("src")?.trim();
      const src = resolveApiAssetUrl(originalSource) ?? originalSource ?? "";
      return {
        src,
        alt: image.alt || `漫画第 ${index + 1} 页`,
      };
    })
    .filter((page) => page.src.length > 0);
}

/**
 * Moves the comic reader to a specific page while keeping only that page mounted.
 * Key parameter: `index` is zero-based and will be clamped. Return value: none.
 * Side effect: updates active page state so the browser requests only the selected image.
 */
function goToComicPage(index: number) {
  if (!comicPages.value.length) {
    return;
  }

  const clampedIndex = Math.min(Math.max(index, 0), comicPages.value.length - 1);
  activeComicPageIndex.value = clampedIndex;
}

/**
 * Limits thumbnail image mounting so the desktop page rail does not download every comic page at once.
 * Key parameter: `index` is the zero-based page position. Return value: true for active/neighbor pages only.
 * Side effect: none; the template uses this to keep distant pages as lightweight placeholders.
 */
function shouldRenderComicThumbnail(index: number) {
  return Math.abs(index - activeComicPageIndex.value) <= 1;
}

/**
 * Handles left/right keyboard pagination for the comic reader shell.
 * Key parameter: `event` is a keyboard event from the focused reader. Return value: none.
 * Side effect: changes the active comic page for ArrowLeft/ArrowRight only.
 */
function handleComicReaderKeydown(event: KeyboardEvent) {
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    goToComicPage(activeComicPageIndex.value - 1);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    goToComicPage(activeComicPageIndex.value + 1);
  }
}

/**
 * Schedules a low-priority background preload for only the next comic page.
 * Key parameters: none; it reads active page state. Return value: none.
 * Side effect: starts one delayed image request, leaving the rendered DOM to the current page only.
 */
function scheduleNextComicPagePreload() {
  if (nextComicPreloadTimer !== null) {
    window.clearTimeout(nextComicPreloadTimer);
    nextComicPreloadTimer = null;
  }

  const nextPage = comicPages.value[activeComicPageIndex.value + 1];
  if (!props.comicReader || !nextPage || prefetchedComicImageUrls.has(nextPage.src)) {
    return;
  }

  nextComicPreloadTimer = window.setTimeout(() => {
    prefetchedComicImageUrls.add(nextPage.src);
    const image = new Image();
    image.decoding = "async";
    image.setAttribute("fetchpriority", "low");
    image.src = nextPage.src;
    nextComicPreloadTimer = null;
  }, 350);
}

/**
 * Decorates the already-sanitized rendered Markdown after Vue mounts or refreshes it.
 * Key parameters: none; it reads `bodyRef` and current props. Return value: none.
 * Side effect: adds heading anchors and resolves API image sources for regular Markdown rendering.
 */
function decorateRenderedContent() {
  decorateHeadingAnchors();
  if (hasComicPages.value) {
    return;
  }
  decorateRenderedImageSources();
}

/**
 * Adds stable anchor IDs to Markdown headings inside this post only.
 * Key parameters: none; it reads `bodyRef` and `post.floor`. Return value: none.
 * Side effect: mutates rendered heading IDs/classes for in-page navigation.
 */
function decorateHeadingAnchors() {
  const container = bodyRef.value;
  if (!container) {
    return;
  }

  container
    .querySelectorAll<HTMLElement>(".markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4")
    .forEach((heading, index) => {
      heading.id = `post-${props.post.floor}-heading-${index}`;
      heading.classList.add("markdown-heading-anchor");
    });
}

/**
 * Rewrites API-relative image paths inside server-rendered Markdown to the configured API origin.
 * Key parameters: none; it reads rendered Markdown under `bodyRef`. Return value: none.
 * Side effect: mutates `<img src>` attributes so `/uploads/...` content loads outside dev proxy contexts.
 */
function decorateRenderedImageSources() {
  const container = bodyRef.value;
  if (!container) {
    return;
  }

  container.querySelectorAll<HTMLImageElement>(".markdown-body img").forEach((image) => {
    const originalSource = image.getAttribute("src")?.trim();
    const resolvedSource = resolveApiAssetUrl(originalSource);
    if (resolvedSource && resolvedSource !== originalSource) {
      image.setAttribute("src", resolvedSource);
    }
  });
}

</script>

<template>
  <UiCard
    class="post-item"
    :class="{
      deleted: post.deleted,
      'post-item--article': variant === 'article',
      'post-item--comic-reader': comicReader,
      'post-item--reply': variant === 'reply',
    }"
  >
    <article ref="bodyRef" class="post-body">
      <header class="post-header">
        <div class="post-author-line">
          <UiAvatar
            :src="post.authorAvatarUrl"
            :name="post.authorName"
            :role="post.authorRole"
            :level="post.authorLevel"
            size="sm"
          />
          <div class="post-author-copy">
            <div class="post-author-name">
              <strong>{{ post.authorName }}</strong>
              <span v-if="post.floor === 1" class="author-badge author-badge--owner">楼主</span>
              <span v-if="authorRoleBadge" class="author-badge author-badge--role">{{ authorRoleBadge }}</span>
            </div>
            <div class="post-meta-line">
              <time :datetime="post.createdAt">{{ relativeTime(post.createdAt) }}</time>
              <span aria-hidden="true">·</span>
              <a class="post-floor-link" :href="`#post-${post.floor}`">#{{ post.floor }}</a>
              <template v-if="editedAfterPublish">
                <span aria-hidden="true">·</span>
                <span>已编辑</span>
              </template>
            </div>
          </div>
        </div>
        <div class="post-header-actions">
          <UiButton v-if="canEdit" class="post-header-edit" tone="subtle" @click="startEdit">
            <EditOutlined aria-hidden="true" />
            编辑
          </UiButton>
        </div>
      </header>
      <div v-if="post.acceptedAnswer" class="accepted-answer-badge">✓ 已采纳解决方案</div>
      <div v-if="post.deleted" class="deleted-copy">该楼层已删除或隐藏。</div>
      <template v-else-if="editing">
        <div class="edit-field">
          <span>编辑本楼层</span>
          <div class="edit-editor-box">
            <MdEditor
              ref="editEditorRef"
              v-model="editDraft"
              :id="`post-edit-editor-${post.id}`"
              class="edit-md-editor"
              language="zh-CN"
              theme="light"
              preview-theme="github"
              code-theme="atom"
              :preview="false"
              :footers="editEditorFooters"
              :toolbars="editEditorToolbars"
              :sanitize="sanitizeEditHtml"
              :transform-img-url="resolveApiAssetUrl"
              :disabled="savingEdit"
              :no-katex="true"
              :no-mermaid="true"
              :no-img-zoom-in="true"
              :show-code-row-number="false"
              placeholder="编辑内容"
              @onUploadImg="handleEditImageUpload"
            />
          </div>
        </div>
        <div class="edit-upload-row">
          <MarkdownUploadButton compact :disabled="savingEdit" @insert="insertEditMarkdownUpload" />
        </div>
        <div class="edit-actions">
          <UiButton tone="primary" :disabled="!editDraft.trim() || savingEdit" @click="saveEdit">
            {{ savingEdit ? "保存中…" : "保存编辑" }}
          </UiButton>
          <UiButton tone="ghost" :disabled="savingEdit" @click="cancelEdit">取消编辑</UiButton>
        </div>
      </template>
      <section
        v-else-if="hasComicPages"
        class="comic-reader"
        aria-label="漫画阅读器"
        tabindex="0"
        @keydown="handleComicReaderKeydown"
      >
        <header class="comic-reader__toolbar">
          <div class="comic-reader__title">
            <span>漫画阅读</span>
            <strong>第 {{ activeComicPageIndex + 1 }} / {{ comicPages.length }} 页</strong>
          </div>

          <div class="comic-reader__nav">
            <button
              type="button"
              :disabled="activeComicPageIndex === 0"
              @click="goToComicPage(activeComicPageIndex - 1)"
            >
              上一页
            </button>
            <button
              type="button"
              :disabled="activeComicPageIndex >= comicPages.length - 1"
              @click="goToComicPage(activeComicPageIndex + 1)"
            >
              下一页
            </button>
          </div>
        </header>

        <div class="comic-reader__stage">
          <figure v-if="activeComicPage" class="comic-reader__single-page">
            <div class="comic-reader__page-frame">
              <button
                class="comic-reader__page-hit comic-reader__page-hit--prev"
                type="button"
                aria-label="上一页"
                :disabled="activeComicPageIndex === 0"
                @click="goToComicPage(activeComicPageIndex - 1)"
              >
                ‹
              </button>
              <img
                :key="activeComicPage.src"
                :src="activeComicPage.src"
                :alt="activeComicPage.alt"
                loading="eager"
                decoding="async"
                fetchpriority="high"
              />
              <button
                class="comic-reader__page-hit comic-reader__page-hit--next"
                type="button"
                aria-label="下一页"
                :disabled="activeComicPageIndex >= comicPages.length - 1"
                @click="goToComicPage(activeComicPageIndex + 1)"
              >
                ›
              </button>
            </div>
          </figure>

          <aside v-if="comicPages.length > 1" class="comic-reader__thumbs" aria-label="漫画页列表">
            <button
              v-for="(page, index) in comicPages"
              :key="page.src"
              class="comic-reader__thumb"
              :class="{ 'comic-reader__thumb--active': index === activeComicPageIndex }"
              type="button"
              :aria-label="`跳到第 ${index + 1} 页`"
              :aria-current="index === activeComicPageIndex ? 'page' : undefined"
              @click="goToComicPage(index)"
            >
              <span>第 {{ index + 1 }} 页</span>
              <img
                v-if="shouldRenderComicThumbnail(index)"
                :src="page.src"
                :alt="page.alt"
                loading="lazy"
                decoding="async"
                fetchpriority="low"
              />
              <span v-else class="comic-reader__thumb-placeholder">{{ index + 1 }}</span>
            </button>
          </aside>
        </div>
      </section>
      <div v-else class="markdown-body" v-html="renderedPostHtml" />
      <p v-if="statusMessage" class="post-status" role="status">{{ statusMessage }}</p>
      <footer v-if="!post.deleted" class="post-action-bar">
        <button
          class="icon-action"
          :class="{ 'is-active': liked }"
          type="button"
          :title="liked ? '取消点赞' : '点赞'"
          :aria-label="`${liked ? '取消点赞' : '点赞'}，当前 ${optimisticLikeCount}`"
          :aria-pressed="liked"
          :disabled="likePending"
          @click="toggleLike"
        >
          <HeartFilled v-if="liked" aria-hidden="true" />
          <HeartOutlined v-else aria-hidden="true" />
          <span v-if="optimisticLikeCount" class="action-count">{{ optimisticLikeCount }}</span>
        </button>
        <button class="icon-action" type="button" title="复制楼层链接" aria-label="复制楼层链接" @click="copyPostLink">
          <LinkOutlined aria-hidden="true" />
        </button>
        <button
          v-if="canToggleSolution"
          class="icon-action"
          :class="{ 'is-active': post.acceptedAnswer }"
          type="button"
          :title="post.acceptedAnswer ? '取消采纳' : '采纳为答案'"
          :aria-label="post.acceptedAnswer ? '取消采纳这个答案' : '采纳这个楼层为答案'"
          :aria-pressed="post.acceptedAnswer"
          :disabled="solutionPending"
          @click="toggleSolution"
        >
          <CheckCircleOutlined v-if="post.acceptedAnswer" aria-hidden="true" />
          <RocketOutlined v-else aria-hidden="true" />
        </button>
        <details ref="postMoreRef" class="post-more" @keydown.esc="closeMoreMenu">
          <summary title="更多操作" aria-label="更多楼层操作">
            <EllipsisOutlined aria-hidden="true" />
          </summary>
          <div class="post-more-menu">
            <button v-if="hasCodeBlock" type="button" @click="copyCode">
              <CodeOutlined aria-hidden="true" />
              复制代码
            </button>
            <button type="button" :disabled="!canFlag" @click="flagPost">
              <FlagOutlined aria-hidden="true" />
              举报
            </button>
            <button v-if="canBlockAuthor" type="button" @click="blockAuthor">
              <UserDeleteOutlined aria-hidden="true" />
              屏蔽用户
            </button>
            <button v-if="canViewHistory" type="button" @click="toggleHistory">
              <HistoryOutlined aria-hidden="true" />
              {{ historyOpen ? "收起历史" : "编辑历史" }}
            </button>
            <button v-if="canDelete" type="button" :disabled="deletingPost" @click="deleteReply">
              <DeleteOutlined aria-hidden="true" />
              {{ deletingPost ? "删除中…" : "删除" }}
            </button>
          </div>
        </details>
        <button class="reply-action" type="button" @click="quotePost">
          <RollbackOutlined aria-hidden="true" />
          <span>回复</span>
          <small v-if="post.replyCount">{{ post.replyCount }}</small>
        </button>
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
    <ReportModal
      :open="reportModalOpen"
      target-type="post"
      :target-id="post.id"
      @close="reportModalOpen = false"
      @success="setStatus('已提交举报')"
    />
  </UiCard>
</template>

<style scoped lang="scss" src="./PostItem.scss"></style>
