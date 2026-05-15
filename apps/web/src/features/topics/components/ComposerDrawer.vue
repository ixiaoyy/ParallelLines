<script setup lang="ts">
import { computed, ref } from "vue";

import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const props = withDefaults(
  defineProps<{
    mode?: "topic" | "reply";
    boardName?: string;
    topicTitle?: string;
    compact?: boolean;
    submitting?: boolean;
  }>(),
  {
    mode: "topic",
    boardName: "支持与排障",
    topicTitle: "",
    compact: false,
    submitting: false,
  },
);
const emit = defineEmits<{ submit: [rawMd: string] }>();

const draft = ref("");
const title = ref("");
const tags = ref("fastapi, 排障");

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

function handleSubmit() {
  const rawMd = draft.value.trim();
  if (!rawMd || props.submitting) {
    return;
  }

  emit("submit", rawMd);
  draft.value = "";
}
</script>

<template>
  <UiCard class="composer" :class="{ 'composer--compact': compact, 'composer--reply': isReplyMode }">
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

    <textarea v-model="draft" :placeholder="placeholder" rows="4" />

    <label v-if="!isReplyMode" class="composer-field composer-field--tags">
      <span>标签</span>
      <input v-model="tags" placeholder="用逗号分隔标签" />
    </label>

    <div class="composer-preview">
      <span>草稿预览</span>
      <p>{{ previewText }}</p>
    </div>

    <footer>
      <UiButton tone="ghost">保存草稿</UiButton>
      <UiButton tone="primary" :disabled="!canSubmit" @click="handleSubmit">
        {{ submitting ? "发布中…" : isReplyMode ? "发布回复" : "创建主题" }}
      </UiButton>
    </footer>
  </UiCard>
</template>

<style scoped lang="scss" src="./ComposerDrawer.scss"></style>
