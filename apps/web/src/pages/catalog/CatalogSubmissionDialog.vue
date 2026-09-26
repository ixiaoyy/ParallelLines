<script setup lang="ts">
import { CheckCircleFilled, CloseOutlined, UploadOutlined } from "@ant-design/icons-vue";
import { nextTick, onUnmounted, ref, watch } from "vue";

import { submitCatalogProject } from "@/features/catalog/submissionsApi";
import UiButton from "@/shared/ui/Button.vue";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ "update:open": [value: boolean] }>();

const dialog = ref<HTMLDialogElement | null>(null);
const coverInput = ref<HTMLInputElement | null>(null);
const categoryName = ref("");
const projectName = ref("");
const url = ref("");
const authorName = ref("");
const contact = ref("");
const cover = ref<File | null>(null);
const coverPreview = ref("");
const coverError = ref("");
const formError = ref("");
const isSubmitting = ref(false);
const isSubmitted = ref(false);

// 每次重新打开表单都使用新草稿，已选图片的本地预览及时释放。
function resetDraft(): void {
  categoryName.value = "";
  projectName.value = "";
  url.value = "";
  authorName.value = "";
  contact.value = "";
  cover.value = null;
  coverError.value = "";
  formError.value = "";
  isSubmitted.value = false;
  if (coverPreview.value) URL.revokeObjectURL(coverPreview.value);
  coverPreview.value = "";
  if (coverInput.value) coverInput.value.value = "";
}

watch(() => props.open, async (open) => {
  if (open) {
    resetDraft();
    await nextTick();
    if (props.open && !dialog.value?.open) dialog.value?.showModal();
  } else if (dialog.value?.open) {
    dialog.value.close();
  }
}, { immediate: true });

onUnmounted(() => {
  if (coverPreview.value) URL.revokeObjectURL(coverPreview.value);
});

function closeDialog(): void {
  if (!isSubmitting.value) dialog.value?.close();
}

function onCancel(event: Event): void {
  if (isSubmitting.value) event.preventDefault();
}

function onClosed(): void {
  emit("update:open", false);
}

// 投稿封面可选，先限制格式与体积，后端仍会独立校验上传内容。
function selectCover(event: Event): void {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0] ?? null;
  coverError.value = "";
  if (coverPreview.value) URL.revokeObjectURL(coverPreview.value);
  coverPreview.value = "";
  cover.value = null;
  if (!file) return;
  if (!/^image\/(?:png|jpeg|gif|webp)$/.test(file.type)) {
    input.value = "";
    coverError.value = "请上传 PNG、JPG、GIF 或 WebP 图片。";
    return;
  }
  if (file.size > 2 * 1024 * 1024) {
    input.value = "";
    coverError.value = "封面图不能超过 2 MB。";
    return;
  }
  cover.value = file;
  coverPreview.value = URL.createObjectURL(file);
}

function clearCover(): void {
  if (coverPreview.value) URL.revokeObjectURL(coverPreview.value);
  coverPreview.value = "";
  cover.value = null;
  coverError.value = "";
  if (coverInput.value) coverInput.value.value = "";
}

// 投稿只写入待审记录；收到 pending 后才显示审核提示，不把项目提前加入公开目录。
async function submit(): Promise<void> {
  if (isSubmitting.value || coverError.value) return;
  formError.value = "";
  let parsedUrl: URL;
  try {
    parsedUrl = new URL(url.value.trim());
    if (parsedUrl.protocol !== "https:" || !parsedUrl.hostname || parsedUrl.username || parsedUrl.password) {
      throw new Error("invalid_url");
    }
  } catch {
    formError.value = "请输入有效的 HTTPS 游戏链接。";
    return;
  }

  isSubmitting.value = true;
  try {
    const result = await submitCatalogProject({
      category_name: categoryName.value.trim(),
      project_name: projectName.value.trim(),
      url: parsedUrl.toString(),
      author_name: authorName.value.trim() || null,
      contact: contact.value.trim() || null,
      cover: cover.value,
    });
    if (result.status !== "pending") throw new Error("unexpected_status");
    isSubmitted.value = true;
  } catch {
    formError.value = "提交失败，请稍后重试。";
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <dialog ref="dialog" class="catalog-submission-dialog" aria-labelledby="catalog-submission-title" @close="onClosed" @cancel="onCancel">
    <div class="catalog-submission-dialog__header">
      <h2 id="catalog-submission-title"><UploadOutlined aria-hidden="true" /> 投稿游戏</h2>
      <button type="button" class="catalog-submission-dialog__close" aria-label="关闭投稿窗口" :disabled="isSubmitting" @click="closeDialog"><CloseOutlined aria-hidden="true" /></button>
    </div>

    <div v-if="isSubmitted" class="catalog-submission-dialog__success" role="status">
      <CheckCircleFilled aria-hidden="true" />
      <p>待审核</p>
      <button type="button" @click="closeDialog">完成</button>
    </div>

    <form v-else class="catalog-submission-dialog__form" @submit.prevent="submit">
      <div class="catalog-submission-dialog__names">
      <label>
        <span>分类名称 <strong>*</strong></span>
        <input v-model="categoryName" name="category_name" type="text" maxlength="120" required autocomplete="off" autofocus placeholder="例如：休闲" />
      </label>
      <label>
        <span>游戏名称 <strong>*</strong></span>
        <input v-model="projectName" name="project_name" type="text" maxlength="120" required autocomplete="off" placeholder="输入游戏名称" />
      </label>
      </div>
      <label>
        <span>游戏链接 <strong>*</strong></span>
        <input v-model="url" name="url" type="url" maxlength="2048" required inputmode="url" placeholder="https://" />
      </label>
      <div class="catalog-submission-dialog__optional">
        <label>
          <span>作者名 <small>选填</small></span>
          <input v-model="authorName" name="author_name" type="text" maxlength="120" autocomplete="name" placeholder="作者或团队名称" />
        </label>
        <label>
          <span>联系方式 <small>选填，仅管理员可见</small></span>
          <input v-model="contact" name="contact" type="text" maxlength="200" autocomplete="email" placeholder="邮箱或其他联系方式" />
        </label>
      </div>
      <div class="catalog-submission-dialog__cover">
        <label id="catalog-submission-cover-label" for="catalog-submission-cover">封面图 <small>选填，最大 2 MB</small></label>
        <!-- 中文按钮触发现有文件选择与校验，避免原生控件受浏览器语言影响。 -->
        <input id="catalog-submission-cover" ref="coverInput" name="cover" type="file" accept="image/png,image/jpeg,image/gif,image/webp" hidden @change="selectCover" />
        <div class="catalog-submission-dialog__cover-picker">
          <button type="button" class="catalog-submission-dialog__choose-cover" aria-describedby="catalog-submission-cover-label" @click="coverInput?.click()">{{ cover ? '更换封面' : '选择封面' }}</button>
          <span v-if="cover" class="catalog-submission-dialog__filename" :title="cover.name">{{ cover.name }}</span>
        </div>
        <img v-if="coverPreview" :src="coverPreview" alt="已选封面预览" />
        <button v-if="coverPreview || coverError" type="button" class="catalog-submission-dialog__clear-cover" @click="clearCover">移除封面</button>
        <p v-if="coverError" role="alert" class="catalog-submission-dialog__error">{{ coverError }}</p>
      </div>
      <p v-if="formError" role="alert" class="catalog-submission-dialog__error">{{ formError }}</p>
      <div class="catalog-submission-dialog__actions">
        <button type="button" :disabled="isSubmitting" @click="closeDialog">取消</button>
        <UiButton type="submit" :disabled="isSubmitting">{{ isSubmitting ? "提交中…" : "提交审核" }}</UiButton>
      </div>
    </form>
  </dialog>
</template>

<style scoped lang="scss" src="./CatalogSubmissionDialog.scss"></style>
