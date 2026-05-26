<script setup lang="ts">
import UiAvatar from "@/shared/ui/Avatar.vue";
import UiBadge from "@/shared/ui/Badge.vue";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";
import UiEmptyState from "@/shared/ui/EmptyState.vue";
import UiSkeleton from "@/shared/ui/Skeleton.vue";
</script>

<template>
  <div class="design-page">
    <header>
      <UiBadge tone="blue">设计令牌</UiBadge>
      <h1>平行线 UI 基线</h1>
      <p>用于前三个任务的设计系统验收页：按钮、卡片、徽章、头像、空状态、代码块。</p>
    </header>

    <section class="swatches">
      <div style="--swatch: var(--bg-app)">背景</div>
      <div style="--swatch: var(--primary)">主色</div>
      <div style="--swatch: var(--accent-geek)">青绿</div>
      <div style="--swatch: var(--accent-coral)">珊瑚</div>
      <div style="--swatch: var(--accent-lime)">柠绿</div>
      <div style="--swatch: var(--accent-gold)">金黄</div>
      <div style="--swatch: var(--title)">标题</div>
      <div style="--swatch: var(--text)">正文</div>
      <div style="--swatch: var(--code-bg)">代码</div>
    </section>

    <div class="grid">
      <UiCard class="panel">
        <h2>操作按钮</h2>
        <div class="inline">
          <UiButton>主操作</UiButton>
          <UiButton tone="success">成功状态</UiButton>
          <UiButton tone="subtle">次级操作</UiButton>
          <UiButton tone="ghost">幽灵按钮</UiButton>
        </div>
      </UiCard>

      <UiCard class="panel">
        <h2>身份与状态</h2>
        <div class="inline">
          <UiAvatar name="Lina" size="lg" />
          <UiAvatar name="Bronze" :level="1" size="lg" />
          <UiAvatar name="Silver" :level="3" size="lg" />
          <UiAvatar name="Gold" :level="5" size="lg" />
          <UiAvatar name="Diamond" :level="7" size="lg" />
          <UiAvatar name="Crystal" :level="9" size="lg" />
          <UiAvatar name="Admin" role="admin" size="lg" />
          <UiBadge tone="green">关注中</UiBadge>
          <UiBadge tone="amber">已置顶</UiBadge>
          <UiBadge>已静音</UiBadge>
        </div>
      </UiCard>

      <UiCard class="panel markdown-body">
        <h2>代码块</h2>
        <pre><code>uv run uvicorn app.main:app --reload</code></pre>
      </UiCard>

      <UiCard class="panel">
        <h2>加载与空状态</h2>
        <UiSkeleton />
        <UiEmptyState title="没有更多主题" description="关注更多版块后，这里会出现新的讨论线索。" />
      </UiCard>
    </div>
  </div>
</template>

<style scoped>
.design-page {
  display: grid;
  gap: 1rem;
}

header {
  border-radius: 1.5rem;
  padding: 2rem;
  background: white;
  box-shadow: var(--shadow-card);
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  margin-top: 0.75rem;
  color: var(--title);
  font-size: clamp(2rem, 5vw, 4rem);
  letter-spacing: -0.07em;
}

p {
  margin-top: 0.55rem;
  line-height: 1.7;
}

.swatches {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 0.8rem;
}

.swatches div {
  min-height: 5rem;
  border-radius: 1rem;
  padding: 0.75rem;
  color: white;
  background: var(--swatch);
  font-weight: 850;
  box-shadow: var(--shadow-card);
}

.swatches div:first-child {
  color: var(--title);
  border: 1px solid var(--border);
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.panel {
  display: grid;
  gap: 1rem;
  padding: 1rem;
}

h2 {
  color: var(--title);
}

.inline {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}

@media (max-width: 860px) {
  .swatches,
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
