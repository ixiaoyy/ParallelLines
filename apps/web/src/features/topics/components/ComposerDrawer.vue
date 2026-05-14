<script setup lang="ts">
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";
</script>

<template>
  <UiCard class="composer">
    <div>
      <strong>发一条新主题</strong>
      <p>把现象、环境和你试过的方法写清楚，在线的人更容易接上。</p>
    </div>
    <textarea placeholder="例如：升级后登录会跳回首页，只有 Edge 复现…" rows="4" />
    <div class="composer-preview">
      <span>草稿预览</span>
      <p>环境：Windows 11 / Edge 126 / 单点登录开启</p>
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
  color: var(--text);
  line-height: 1.55;
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

.composer-preview {
  display: grid;
  gap: 0.3rem;
  border: 1px dashed var(--border);
  border-radius: 1rem;
  padding: 0.75rem 0.9rem;
  background: rgba(59, 130, 246, 0.06);
}

.composer-preview span {
  color: var(--primary);
  font-size: 0.76rem;
  font-weight: 860;
}

.composer-preview p {
  margin: 0;
  color: var(--text);
  font-size: 0.86rem;
}
</style>
