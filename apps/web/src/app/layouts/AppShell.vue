<script setup lang="ts">
import { BellOutlined, PlusOutlined, SearchOutlined } from "@ant-design/icons-vue";

import NotificationBell from "@/features/notifications/components/NotificationBell.vue";
import UiButton from "@/shared/ui/Button.vue";
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand" to="/" aria-label="ParallelLines home">
        <span class="brand-mark">PL</span>
        <span>
          <strong>ParallelLines</strong>
          <small>calm technical forum</small>
        </span>
      </RouterLink>

      <nav class="nav-links" aria-label="主导航">
        <RouterLink to="/">最新</RouterLink>
        <a href="#hot">热门</a>
        <a href="#boards">版块</a>
        <RouterLink to="/design-system">设计系统</RouterLink>
      </nav>

      <a-input
        class="search-box"
        placeholder="搜索主题、标签、作者"
        aria-label="搜索 ParallelLines"
      >
        <template #prefix>
          <SearchOutlined />
        </template>
      </a-input>

      <div class="topbar-actions">
        <NotificationBell :count="3">
          <BellOutlined />
        </NotificationBell>
        <UiButton tone="primary">
          <template #icon>
            <PlusOutlined />
          </template>
          发布主题
        </UiButton>
      </div>
    </header>

    <main class="shell-main">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  background:
    radial-gradient(circle at 10% 8%, rgba(59, 130, 246, 0.11), transparent 28rem),
    radial-gradient(circle at 90% 3%, rgba(16, 185, 129, 0.12), transparent 24rem),
    var(--bg-app);
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: grid;
  grid-template-columns: auto auto minmax(14rem, 1fr) auto;
  gap: 1rem;
  align-items: center;
  padding: 1rem clamp(1rem, 3vw, 2.5rem);
  border-bottom: 1px solid rgba(229, 231, 235, 0.8);
  background: rgba(248, 249, 250, 0.86);
  backdrop-filter: blur(18px);
}

.brand {
  display: inline-flex;
  gap: 0.75rem;
  align-items: center;
  color: var(--title);
  text-decoration: none;
}

.brand-mark {
  display: grid;
  width: 2.55rem;
  height: 2.55rem;
  place-items: center;
  border-radius: 0.9rem;
  color: white;
  font-weight: 800;
  letter-spacing: -0.06em;
  background: linear-gradient(135deg, var(--primary), var(--accent-geek));
  box-shadow: 0 14px 28px rgba(59, 130, 246, 0.24);
}

.brand small {
  display: block;
  color: var(--muted);
  font-size: 0.72rem;
}

.nav-links {
  display: flex;
  gap: 0.4rem;
}

.nav-links a {
  padding: 0.55rem 0.75rem;
  border-radius: 999px;
  color: var(--text);
  text-decoration: none;
  font-weight: 650;
}

.nav-links a:hover,
.nav-links a.router-link-active {
  color: var(--primary);
  background: rgba(59, 130, 246, 0.09);
}

.search-box {
  width: 100%;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.86);
}

.topbar-actions {
  display: inline-flex;
  gap: 0.75rem;
  align-items: center;
}

.shell-main {
  width: min(1440px, calc(100% - 2rem));
  margin: 0 auto;
  padding: 1.4rem 0 4rem;
}

@media (max-width: 920px) {
  .topbar {
    grid-template-columns: 1fr auto;
  }

  .nav-links,
  .search-box {
    display: none;
  }
}
</style>
