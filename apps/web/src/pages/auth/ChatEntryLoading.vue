<script setup lang="ts">
import { uiText } from "@/shared/i18n/locale";
import LanguageSwitcher from "@/shared/ui/LanguageSwitcher.vue";
withDefaults(defineProps<{ label?: string }>(), { label: "正在进入聊天…" });
</script>

<template>
  <main class="chat-entry-loading" role="status" aria-live="polite" aria-busy="true">
    <LanguageSwitcher class="auth-language-switcher" />
    <p>{{ uiText(label) }}</p>
  </main>
</template>

<style scoped>
.auth-language-switcher { position: fixed; top: 12px; right: 16px; z-index: 40; }
.chat-entry-loading {
  min-height: 100svh;
  display: grid;
  place-items: center;
  padding: 1.5rem;
  background: var(--bg-app);
  color: var(--text);
}
</style>
