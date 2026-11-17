<script setup lang="ts">
import { uiText } from "@/shared/i18n/locale";
import LanguageSwitcher from "@/shared/ui/LanguageSwitcher.vue";
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { beginCircleLogin } from "@/features/auth/unified/session";
import UiButton from "@/shared/ui/Button.vue";
import ChatEntryLoading from "./ChatEntryLoading.vue";

const route = useRoute();
const error = ref("");
async function connect(): Promise<void> {
  error.value = "";
  try { await beginCircleLogin(route.query.redirect); }
  catch (failure) { error.value = failure instanceof Error ? failure.message : "无法打开主站登录，请重试。"; }
}
onMounted(() => { void connect(); });
</script>
<template>
  <ChatEntryLoading v-if="!error" :label="uiText('正在登录…')" />
  <main v-else class="unified-auth-error" aria-live="polite"><LanguageSwitcher style="position: fixed; top: 12px; right: 16px; z-index: 40" /><h1>{{ uiText("登录") }}</h1><p role="alert">{{ uiText(error) }}</p><UiButton @click="connect">{{ uiText("重试") }}</UiButton><RouterLink to="/">{{ uiText("返回圈子") }}</RouterLink></main>
</template>
<style scoped>.unified-auth-error { max-width: 640px; margin: 64px auto; padding: 24px; }.unified-auth-error a { margin-left: 20px; }</style>
