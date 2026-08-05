<script setup lang="ts">
import {
  CheckCircleFilled,
  DeleteOutlined,
  DownloadOutlined,
  FilePdfOutlined,
  LoadingOutlined,
  LockOutlined,
  SafetyCertificateOutlined,
  TranslationOutlined,
  UploadOutlined,
} from "@ant-design/icons-vue";
import { message as toast } from "ant-design-vue";
import { computed, onBeforeUnmount, ref } from "vue";

import { ApiError } from "@/shared/api/client";
import UiButton from "@/shared/ui/Button.vue";

import type { PdfTranslationDownload } from "../model";
import {
  usePdfTranslationCapabilities,
  useTranslatePdfToEnglish,
} from "../queries";

const selectedFile = ref<File | null>(null);
const dragActive = ref(false);
const visibleError = ref("");
const completedDownload = ref<PdfTranslationDownload | null>(null);
const downloadUrl = ref("");

const capabilitiesQuery = usePdfTranslationCapabilities();
const translateMutation = useTranslatePdfToEnglish();

const capabilities = computed(() => capabilitiesQuery.data.value);
const maxFileSize = computed(() => capabilities.value?.max_bytes ?? 10 * 1024 * 1024);
const maxPageCount = computed(() => capabilities.value?.max_pages ?? 30);
const canTranslate = computed(
  () =>
    Boolean(selectedFile.value) &&
    capabilities.value?.ai_enabled === true &&
    !translateMutation.isPending.value,
);
const selectedFileSize = computed(() =>
  selectedFile.value ? formatBytes(selectedFile.value.size) : "",
);

onBeforeUnmount(revokeDownloadUrl);

/**
 * Accepts a native input selection and validates only the first PDF.
 * Key parameter: browser change event. Return value: none.
 * Side effect: replaces the current file and clears any prior result.
 */
function onFileInput(event: Event): void {
  const input = event.target as HTMLInputElement;
  selectFile(input.files?.[0] ?? null);
  input.value = "";
}

/**
 * Accepts a dropped file while preserving the native input as the accessible path.
 * Key parameter: browser drag event. Return value: none.
 * Side effect: updates drag state and selected file.
 */
function onDrop(event: DragEvent): void {
  dragActive.value = false;
  if (translateMutation.isPending.value) return;
  selectFile(event.dataTransfer?.files?.[0] ?? null);
}

/**
 * Validate and store one PDF against the server-owned byte limit.
 * Key parameter: optional browser File. Return value: none.
 * Side effect: clears prior errors/downloads or records a visible validation error.
 */
function selectFile(file: File | null): void {
  if (translateMutation.isPending.value) return;
  visibleError.value = "";
  clearCompletedDownload();
  if (!file) {
    selectedFile.value = null;
    return;
  }
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    selectedFile.value = null;
    visibleError.value = "请选择 .pdf 文件。";
    return;
  }
  if (file.size > maxFileSize.value) {
    selectedFile.value = null;
    visibleError.value = `文件不能超过 ${formatBytes(maxFileSize.value)}。`;
    return;
  }
  selectedFile.value = file;
}

/**
 * Run the strict server workflow and retain a reusable browser download URL.
 * Key parameters: none. Return value: promise resolved after success or visible failure.
 * Side effect: uploads the selected file and creates a temporary browser object URL.
 */
async function translateSelectedFile(): Promise<void> {
  const file = selectedFile.value;
  if (!file || !canTranslate.value) return;
  visibleError.value = "";
  clearCompletedDownload();
  try {
    const result = await translateMutation.mutateAsync(file);
    completedDownload.value = result;
    downloadUrl.value = URL.createObjectURL(result.blob);
    toast.success("纯英文 PDF 已通过双重检查");
  } catch (error) {
    const fallback = "PDF 英文化失败，请稍后重试。";
    visibleError.value = error instanceof ApiError || error instanceof Error ? error.message : fallback;
    toast.error(visibleError.value || fallback);
  }
}

/**
 * Trigger a normal browser download for the verified result.
 * Key parameters: none. Return value: none.
 * Side effect: clicks a short-lived anchor bound to the object URL.
 */
function downloadResult(): void {
  const result = completedDownload.value;
  if (!result || !downloadUrl.value) return;
  const anchor = document.createElement("a");
  anchor.href = downloadUrl.value;
  anchor.download = result.filename;
  anchor.rel = "noopener";
  anchor.click();
}

/**
 * Remove the selected input and any completed result.
 * Key parameters: none. Return value: none.
 * Side effect: revokes the object URL and resets local workflow state.
 */
function resetWorkspace(): void {
  selectedFile.value = null;
  visibleError.value = "";
  clearCompletedDownload();
}

/**
 * Clear result metadata and release its browser object URL.
 * Key parameters: none. Return value: none.
 * Side effect: revokes an existing object URL.
 */
function clearCompletedDownload(): void {
  revokeDownloadUrl();
  completedDownload.value = null;
}

/**
 * Revoke the current browser download URL exactly once.
 * Key parameters: none. Return value: none.
 * Side effect: releases browser Blob memory.
 */
function revokeDownloadUrl(): void {
  if (!downloadUrl.value) return;
  URL.revokeObjectURL(downloadUrl.value);
  downloadUrl.value = "";
}

/**
 * Format byte counts for visible upload limits and file summaries.
 * Key parameter: non-negative byte count. Return value: compact human-readable text.
 * Side effect: none.
 */
function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(bytes >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
}
</script>

<template>
  <section class="pdf-translation-workspace" aria-labelledby="pdf-translation-title">
    <header class="pdf-translation-header">
      <div>
        <span class="pdf-translation-header__eyebrow">社区工具箱 / DOCUMENT LAB</span>
        <h1 id="pdf-translation-title">中文 PDF，转成纯英文报告</h1>
        <p>保留章节、表格和专业版式；中文正文、标题、页眉页脚及水印全部进入翻译与残留检查。</p>
      </div>
      <span class="pdf-translation-header__stamp"><SafetyCertificateOutlined aria-hidden="true" /> ENGLISH ONLY</span>
    </header>

    <div class="pdf-translation-layout">
      <aside class="pdf-translation-process" aria-label="处理流程">
        <span class="pdf-translation-process__label">PROCESS</span>
        <ol>
          <li><span>01</span><div><strong>读取与 OCR</strong><small>文本层、扫描件与水印</small></div></li>
          <li><span>02</span><div><strong>专业英译</strong><small>专有名词统一英文转写</small></div></li>
          <li><span>03</span><div><strong>重建与复核</strong><small>文本层 + 页面 OCR 双检</small></div></li>
        </ol>
        <p><LockOutlined aria-hidden="true" /> 不进入论坛附件库，不保存转换历史。</p>
      </aside>

      <main class="pdf-translation-console">
        <p v-if="capabilitiesQuery.isLoading.value" class="pdf-translation-state" role="status">
          正在读取转换服务能力…
        </p>
        <p v-else-if="capabilitiesQuery.isError.value" class="pdf-translation-state is-error" role="alert">
          无法读取 PDF 转换服务，请刷新页面重试。
        </p>
        <p v-else-if="capabilities && !capabilities.ai_enabled" class="pdf-translation-state is-error" role="alert">
          站点尚未配置 PDF 翻译模型。为避免输出残留中文的无效文件，本工具暂不提供本地降级。
        </p>
        <p v-if="visibleError" class="pdf-translation-state is-error" role="alert">{{ visibleError }}</p>

        <form class="pdf-translation-form" @submit.prevent="translateSelectedFile">
          <div class="pdf-translation-form__heading">
            <div><span>INPUT</span><h2>上传原始中文 PDF</h2></div>
            <small>最多 {{ formatBytes(maxFileSize) }} / {{ maxPageCount }} 页</small>
          </div>

          <label
            class="pdf-dropzone"
            :class="{ 'is-active': dragActive, 'has-file': selectedFile }"
            @dragenter.prevent="dragActive = true"
            @dragover.prevent="dragActive = true"
            @dragleave.prevent="dragActive = false"
            @drop.prevent="onDrop"
          >
            <input type="file" accept="application/pdf,.pdf" :disabled="translateMutation.isPending.value" @change="onFileInput" />
            <span class="pdf-dropzone__icon"><FilePdfOutlined aria-hidden="true" /></span>
            <template v-if="selectedFile">
              <strong>{{ selectedFile.name }}</strong>
              <small>{{ selectedFileSize }} · 已准备进行严格英文化</small>
            </template>
            <template v-else>
              <strong>拖入 PDF，或点击选择文件</strong>
              <small>支持文本型与扫描型 PDF；加密文件暂不支持</small>
            </template>
            <span class="pdf-dropzone__action"><UploadOutlined aria-hidden="true" /> 选择 PDF</span>
          </label>

          <div class="pdf-translation-contract" aria-label="输出保证">
            <span><CheckCircleFilled aria-hidden="true" /> 不保留中文标题、页眉、页脚、水印</span>
            <span><CheckCircleFilled aria-hidden="true" /> 公司名称英文转写，人名使用拼音</span>
            <span><CheckCircleFilled aria-hidden="true" /> 保留编号、日期、金额和地址事实</span>
            <span><CheckCircleFilled aria-hidden="true" /> 表格全部英文化并保留阅读结构</span>
          </div>

          <p v-if="capabilities" class="pdf-translation-privacy">{{ capabilities.privacy_notice }}</p>

          <div class="pdf-translation-actions">
            <UiButton type="submit" tone="primary" :disabled="!canTranslate">
              <template #icon>
                <LoadingOutlined v-if="translateMutation.isPending.value" aria-hidden="true" />
                <TranslationOutlined v-else aria-hidden="true" />
              </template>
              {{ translateMutation.isPending.value ? "正在英文化并双重检查…" : "生成纯英文 PDF" }}
            </UiButton>
            <UiButton v-if="selectedFile" tone="ghost" :disabled="translateMutation.isPending.value" @click="resetWorkspace">
              <template #icon><DeleteOutlined aria-hidden="true" /></template>移除文件
            </UiButton>
          </div>
        </form>

        <section v-if="translateMutation.isPending.value" class="pdf-translation-pending" role="status" aria-live="polite">
          <div class="pdf-translation-pending__track"><span></span></div>
          <div><strong>正在处理整份文档</strong><p>OCR、专有名词统一、版式重建和最终残留检查会依次完成，请勿关闭页面。</p></div>
        </section>

        <section v-if="completedDownload" class="pdf-translation-result" aria-labelledby="pdf-result-title">
          <span class="pdf-translation-result__mark"><CheckCircleFilled aria-hidden="true" /></span>
          <div>
            <span>VERIFIED OUTPUT</span>
            <h2 id="pdf-result-title">纯英文 PDF 已就绪</h2>
            <p>
              {{ completedDownload.pageCount ? `${completedDownload.pageCount} 页` : "页数已核对" }}
              <template v-if="completedDownload.translatedSegments"> · {{ completedDownload.translatedSegments }} 个中文区域已英文化</template>
            </p>
            <small>请对法律、专利、证书和财务内容进行人工复核后再正式使用。</small>
          </div>
          <UiButton tone="success" @click="downloadResult">
            <template #icon><DownloadOutlined aria-hidden="true" /></template>下载 {{ completedDownload.filename }}
          </UiButton>
        </section>
      </main>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./PdfTranslationWorkspace.scss"></style>
