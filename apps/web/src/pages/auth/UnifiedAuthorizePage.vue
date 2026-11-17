<script setup lang="ts">
import { uiText } from "@/shared/i18n/locale";
import LanguageSwitcher from "@/shared/ui/LanguageSwitcher.vue";
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { authorizeCircle, UnifiedApiError } from "@/features/auth/unified/api";
import { CALLBACK_PATH, CIRCLE_CLIENT_ID, mainAuthOrigin, statusClientOrigin, UNIFIED_AUTH_ENABLED } from "@/features/auth/unified/protocol";
import { ensurePrimarySession } from "@/features/auth/unified/session";
import UiButton from "@/shared/ui/Button.vue";
import ChatEntryLoading from "./ChatEntryLoading.vue";

const route = useRoute();
const router = useRouter();
const error = ref("");
const pending = ref(false);
const silent = window.parent !== window || route.query.silent === "1";

/** 先校验固定回调再做任何导航；匿名的隐藏请求只返回未登录，不在子站内挂密码页面。 */
async function connect(): Promise<void> {
  if (pending.value) return;
  pending.value = true;
  error.value = "";
  const { client_id: clientId, redirect_uri: redirectUri, state, code_challenge: challenge, code_challenge_method: method } = route.query;
  const expectedCallback = statusClientOrigin("circle") + CALLBACK_PATH;
  if (!UNIFIED_AUTH_ENABLED || window.location.origin !== mainAuthOrigin() || clientId !== CIRCLE_CLIENT_ID
    || redirectUri !== expectedCallback || typeof state !== "string" || !/^[A-Za-z0-9_-]{8,128}$/.test(state)
    || typeof challenge !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(challenge) || method !== "S256") {
    pending.value = false; error.value = "登录链接已失效，请返回圈子重试。"; return;
  }
  try {
    const session = await ensurePrimarySession();
    if (!session) {
      if (silent) {
        const callback = new URL(expectedCallback);
        callback.search = new URLSearchParams({ error: "login_required", state }).toString();
        window.location.replace(callback.href);
      } else await router.replace({ name: "auth", query: { redirect: route.fullPath, unified: "1" } });
      return;
    }
    const destination = new URL(await authorizeCircle({ redirect_uri: redirectUri, state, code_challenge: challenge }));
    if (destination.origin !== new URL(expectedCallback).origin || destination.pathname !== CALLBACK_PATH
      || destination.username || destination.password || destination.hash || destination.searchParams.get("state") !== state
      || !/^[A-Za-z0-9_-]{32,128}$/.test(destination.searchParams.get("code") || "")) throw new Error("invalid_redirect");
    window.location.replace(destination.href);
  } catch (failure) {
    if (silent) {
      const callback = new URL(expectedCallback);
      callback.search = new URLSearchParams({ error: failure instanceof UnifiedApiError && failure.status === 401 ? "login_required" : "unavailable", state }).toString();
      window.location.replace(callback.href);
    } else error.value = "登录未完成，请重试。";
    pending.value = false;
  }
}
onMounted(() => { void connect(); });
</script>

<template>
  <ChatEntryLoading v-if="!error" :label="uiText('正在登录…')" />
  <main v-else class="unified-auth-error" aria-live="polite"><LanguageSwitcher style="position: fixed; top: 12px; right: 16px; z-index: 40" /><h1>{{ uiText("登录") }}</h1><p role="alert">{{ uiText(error) }}</p><UiButton :disabled="pending" @click="connect">{{ uiText("重试") }}</UiButton><RouterLink to="/">{{ uiText("返回首页") }}</RouterLink></main>
</template>

<style scoped>.unified-auth-error { max-width: 640px; margin: 64px auto; padding: 24px; }.unified-auth-error a { margin-left: 20px; }</style>
