<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { finishUnifiedLogout } from "@/features/auth/unified/api";
import { mainAuthOrigin, statusClientOrigin, UNIFIED_AUTH_ENABLED } from "@/features/auth/unified/protocol";
import { clearUnifiedAccess, ensurePrimarySession, notifyUnifiedChange } from "@/features/auth/unified/session";
import UiButton from "@/shared/ui/Button.vue";
import ChatEntryLoading from "./ChatEntryLoading.vue";

const route = useRoute();
const error = ref("");
const pending = ref(false);
const changedAccount = ref(false);

/** GET页面没有有效出票就绝不自动logout；旧票据也不能清掉后来切换的新账号。 */
async function finish(): Promise<void> {
  if (pending.value) return;
  const ticket = route.query.ticket;
  if (!UNIFIED_AUTH_ENABLED || window.parent !== window || window.location.origin !== mainAuthOrigin()
    || typeof ticket !== "string" || !/^[A-Za-z0-9_-]{32,128}$/.test(ticket)) {
    error.value = "退出链接已失效，请返回后重新操作。"; return;
  }
  pending.value = true;
  error.value = "";
  try {
    const result = await finishUnifiedLogout(ticket);
    if (result.authenticated) {
      await ensurePrimarySession();
      changedAccount.value = true;
    } else await clearUnifiedAccess();
    notifyUnifiedChange();
    if (result.authenticated) return;
    const allowed = [mainAuthOrigin(), statusClientOrigin("circle"), statusClientOrigin("chat"), statusClientOrigin("newapi")];
    const destination = result.return_url ? new URL(result.return_url) : new URL("/", mainAuthOrigin());
    if (!allowed.includes(destination.origin) || destination.pathname !== "/" || destination.search || destination.hash
      || destination.username || destination.password) throw new Error("退出回跳地址无效。");
    window.location.replace(destination.href);
  } catch { error.value = "退出未完成，请重试。"; }
  finally { pending.value = false; }
}
onMounted(() => { void finish(); });
</script>

<template>
  <ChatEntryLoading v-if="pending" label="正在退出…" />
  <main v-else class="unified-auth-error" aria-live="polite"><h1>退出登录</h1><p v-if="changedAccount">账号已切换，请返回后重新操作。</p><p v-if="error" role="alert">{{ error }}</p><UiButton v-if="error" @click="finish">重试</UiButton><RouterLink to="/">返回首页</RouterLink></main>
</template>

<style scoped>.unified-auth-error { max-width: 640px; margin: 64px auto; padding: 24px; }.unified-auth-error a { margin-left: 20px; }</style>
