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
        <a href="#top">Top</a>
        <a href="#boards">Categories</a>
        <a href="#hot">热门</a>
        <a href="#votes">Votes</a>
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

<style scoped lang="scss" src="./AppShell.scss"></style>
