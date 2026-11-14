<script setup lang="ts">
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
  <ChatEntryLoading v-if="!error" label="正在登录…" />
  <main v-else class="unified-auth-error" aria-live="polite"><h1>登录</h1><p role="alert">{{ error }}</p><UiButton @click="connect">重试</UiButton><RouterLink to="/">返回圈子</RouterLink></main>
</template>
<style scoped>.unified-auth-error { max-width: 640px; margin: 64px auto; padding: 24px; }.unified-auth-error a { margin-left: 20px; }</style>
