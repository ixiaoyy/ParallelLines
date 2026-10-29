<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { apiPost, hasAccessToken } from "@/shared/api/client";
import { trustedChatFinish } from "@/shared/router/authReturn";
import UiButton from "@/shared/ui/Button.vue";

const route = useRoute();
const router = useRouter();
const pending = ref(false);
const error = ref("");
let controller: AbortController | null = null;
let requestTimer: number | undefined;
let navigationTimer: number | undefined;
let submittedForm: HTMLFormElement | null = null;
let disposed = false;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Prove main login over its normal bearer API, then POST only the one-time approval to the OP. */
async function connectChat(): Promise<void> {
  if (pending.value) return;
  error.value = "";
  const interactionId = route.query.interaction_id;
  if (typeof interactionId !== "string" || !/^[A-Za-z0-9_-]{8,128}$/.test(interactionId)) {
    error.value = "聊天登录请求无效，请从聊天入口重新进入。";
    return;
  }
  if (!hasAccessToken()) {
    try { await router.replace({ name: "auth", query: { redirect: route.fullPath } }); }
    catch { error.value = "无法打开主站登录，请重试。"; }
    return;
  }
  pending.value = true;
  controller = new AbortController();
  requestTimer = window.setTimeout(() => controller?.abort(), 15_000);
  try {
    const approval = await apiPost<unknown, { interaction_id: string }>(
      "/auth/chat-sso/approve", { interaction_id: interactionId }, { signal: controller.signal },
    );
    window.clearTimeout(requestTimer);
    if (disposed) return;
    if (!isRecord(approval) || approval.interaction_id !== interactionId
      || typeof approval.approval_code !== "string"
      || !/^[A-Za-z0-9_-]{32,128}$/.test(approval.approval_code)) {
      throw new Error("invalid_approval");
    }
    const finish = trustedChatFinish(approval.finish_url, window.location.origin);
    if (!finish) throw new Error("invalid_finish");
    submittedForm?.remove();
    const form = document.createElement("form");
    form.method = "POST";
    form.action = finish;
    form.hidden = true;
    for (const [name, value] of Object.entries({ interaction_id: interactionId, approval_code: approval.approval_code })) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = name;
      input.value = value;
      form.append(input);
    }
    document.body.append(form);
    submittedForm = form;
    form.submit();
    navigationTimer = window.setTimeout(() => {
      if (disposed) return;
      pending.value = false;
      error.value = "聊天跳转未完成，请重试。";
      submittedForm?.remove();
      submittedForm = null;
    }, 10_000);
  } catch {
    if (disposed) return;
    submittedForm?.remove();
    submittedForm = null;
    pending.value = false;
    error.value = "聊天登录未完成：会话可能已过期或此账号尚未获聊天授权。请重新登录或联系管理员。";
  } finally {
    window.clearTimeout(requestTimer);
  }
}

onMounted(() => { void connectChat(); });
onBeforeUnmount(() => {
  disposed = true;
  controller?.abort();
  window.clearTimeout(requestTimer);
  window.clearTimeout(navigationTimer);
  submittedForm?.remove();
});
</script>

<template>
  <main aria-live="polite">
    <h1>进入聊天</h1>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-else>正在验证平行线登录，请稍候。</p>
    <UiButton v-if="error" :disabled="pending" @click="connectChat">重试</UiButton>
    <RouterLink to="/games">返回游戏</RouterLink>
  </main>
</template>
