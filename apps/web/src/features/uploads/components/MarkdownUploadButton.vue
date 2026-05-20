<script setup lang="ts">
import { computed, ref } from "vue";

import { ApiError, getApiUrl } from "@/shared/api/client";
import UiButton from "@/shared/ui/Button.vue";

import { toMarkdownUpload } from "../model";
import { useUploadFile } from "../queries";

const props = withDefaults(
  defineProps<{
    disabled?: boolean;
    compact?: boolean;
  }>(),
  {
    disabled: false,
    compact: false,
  },
);

const emit = defineEmits<{ insert: [markdown: string] }>();

const fileInput = ref<HTMLInputElement | null>(null);
const statusMessage = ref("");
const uploadMutation = useUploadFile();

const canChooseFile = computed(() => !props.disabled && !uploadMutation.isPending.value);

function openFilePicker() {
  if (!canChooseFile.value) {
    return;
  }

  fileInput.value?.click();
}

async function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) {
    return;
  }

  statusMessage.value = "";
  try {
    const upload = await uploadMutation.mutateAsync({ file, kind: "post_attachment" });
    emit("insert", toMarkdownUpload(upload, getApiUrl(upload.url)));
    statusMessage.value = `${upload.original_filename} 已上传，引用已插入正文。`;
  } catch (error) {
    statusMessage.value = uploadErrorMessage(error);
  }
}

function uploadErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "upload_too_large") {
      return "文件超过当前上传大小限制。";
    }
    if (error.code === "upload_type_not_allowed" || error.code === "upload_mime_mismatch") {
      return "文件类型不被允许，或内容与扩展名不一致。";
    }
  }

  return "上传失败：请确认已登录且文件类型安全。";
}
</script>

<template>
  <div class="markdown-upload" :class="{ 'markdown-upload--compact': compact }">
    <input
      ref="fileInput"
      class="markdown-upload__input"
      type="file"
      accept="image/png,image/jpeg,image/gif,image/webp,application/pdf,text/plain,text/markdown,.md,.txt,.log,.csv,.zip"
      @change="handleFileChange"
    />
    <UiButton type="button" tone="ghost" :disabled="!canChooseFile" @click="openFilePicker">
      {{ uploadMutation.isPending.value ? "上传中…" : "上传图片/附件" }}
    </UiButton>
    <span v-if="statusMessage" class="markdown-upload__status" role="status">{{ statusMessage }}</span>
  </div>
</template>

<style scoped lang="scss" src="./MarkdownUploadButton.scss"></style>
