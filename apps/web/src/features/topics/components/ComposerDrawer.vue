<script setup lang="ts">
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";
</script>

<template>
  <UiCard class="composer">
    <div>
      <strong>快速草稿</strong>
      <p>Markdown + 服务端净化预览将在核心内容任务中接入。</p>
    </div>
    <textarea placeholder="写下你的问题、经验或提案…" rows="4" />
    <div class="composer-preview markdown-body">
      <pre><code>const 主题 = await 创建主题({ 版块, 标题, 正文Markdown })</code></pre>
    </div>
    <footer>
      <UiButton tone="ghost">保存草稿</UiButton>
      <UiButton tone="primary">创建主题</UiButton>
    </footer>
  </UiCard>
</template>

<style scoped>
.composer {
  display: grid;
  gap: 0.85rem;
  padding: 1rem;
}

strong {
  color: var(--title);
}

p {
  margin: 0.2rem 0 0;
}

textarea {
  width: 100%;
  resize: vertical;
  border: 1px solid var(--border);
  border-radius: 1rem;
  padding: 0.9rem;
  color: var(--title);
  background: rgba(255, 255, 255, 0.8);
}

textarea:focus {
  outline: 3px solid rgba(59, 130, 246, 0.15);
  border-color: var(--primary);
}

footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
}
</style>
