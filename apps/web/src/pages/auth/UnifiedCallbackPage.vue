<script setup lang="ts">
import { uiText } from "@/shared/i18n/locale";
import LanguageSwitcher from "@/shared/ui/LanguageSwitcher.vue";
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { exchangeCircle } from "@/features/auth/unified/api";
import { CALLBACK_PATH, clearCircleTransaction, localReturnPath, readCircleTransaction, UNIFIED_AUTH_ENABLED } from "@/features/auth/unified/protocol";
import { ACCESS_RESULT_TYPE, applyUnifiedAccess, beginCircleLogin } from "@/features/auth/unified/session";
import { IS_FORUM_SITE } from "@/shared/site/links";
import UiButton from "@/shared/ui/Button.vue";
import ChatEntryLoading from "./ChatEntryLoading.vue";

const route = useRoute();
const router = useRouter();
const error = ref("");
let returnTo = "/";

onMounted(async () => {
  const code = route.query.code;
  const state = route.query.state;
  const failure = route.query.error;
  // 一次码先移出地址栏，避免第三方资源和重载继续携带；verifier始终只在Circle标签会话中。
  history.replaceState(history.state, "", CALLBACK_PATH);
  try {
    if (!UNIFIED_AUTH_ENABLED || !IS_FORUM_SITE) throw new Error("请从圈子重新开始登录。");
    const transaction = readCircleTransaction(state, sessionStorage);
    returnTo = localReturnPath(transaction.returnTo, window.location.origin);
    const inFrame = window.parent !== window;
    if (inFrame !== (transaction.mode === "silent")) throw new Error("登录窗口不匹配，请重新登录。");
    if (failure) {
      clearCircleTransaction(sessionStorage);
      if (inFrame) {
        window.parent.postMessage({ type: ACCESS_RESULT_TYPE, version: 1, state,
          error: failure === "login_required" ? "login_required" : "unavailable" }, window.location.origin);
        return;
      }
      throw new Error("登录未完成，请重试。");
    }
    if (typeof code !== "string" || !/^[A-Za-z0-9_-]{32,128}$/.test(code)) throw new Error("登录回调无效，请重试。");
    const access = await exchangeCircle({ redirect_uri: window.location.origin + CALLBACK_PATH, code, code_verifier: transaction.verifier });
    clearCircleTransaction(sessionStorage);
    if (inFrame) {
      // 同源父页面先切换响应上下文再保存token，隐藏帧本身不抢先改父标签的账户凭据。
      window.parent.postMessage({ type: ACCESS_RESULT_TYPE, version: 1, state, access }, window.location.origin);
      return;
    }
    await applyUnifiedAccess(access);
    await router.replace(returnTo);
  } catch (failure) {
    error.value = failure instanceof Error ? failure.message : "登录未完成，请重试。";
    if (window.parent !== window && typeof state === "string") {
      window.parent.postMessage({ type: ACCESS_RESULT_TYPE, version: 1, state, error: "unavailable" }, window.location.origin);
    }
  }
});
</script>

<template>
  <ChatEntryLoading v-if="!error" :label="uiText('正在登录…')" />
  <main v-else class="unified-auth-error" aria-live="polite"><LanguageSwitcher style="position: fixed; top: 12px; right: 16px; z-index: 40" /><h1>{{ uiText("登录") }}</h1><p role="alert">{{ uiText(error) }}</p><UiButton @click="beginCircleLogin(returnTo)">{{ uiText("重新登录") }}</UiButton><RouterLink to="/">{{ uiText("返回圈子") }}</RouterLink></main>
</template>

<style scoped>.unified-auth-error { max-width: 640px; margin: 64px auto; padding: 24px; }.unified-auth-error a { margin-left: 20px; }</style>
