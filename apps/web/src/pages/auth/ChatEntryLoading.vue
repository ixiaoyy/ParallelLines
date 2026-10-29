<template>
  <main class="chat-entry-loading" role="status" aria-live="polite" aria-busy="true">
    <p>正在进入聊天…</p>
  </main>
</template>

<style scoped>
.chat-entry-loading {
  min-height: 100svh;
  display: grid;
  place-items: center;
  padding: 1.5rem;
  background: var(--bg-app);
  color: var(--text);
}
</style>
