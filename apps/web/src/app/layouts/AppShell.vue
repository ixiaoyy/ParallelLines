<script setup lang="ts">
import { BellOutlined, PlusOutlined, SearchOutlined } from "@ant-design/icons-vue";

import NotificationBell from "@/features/notifications/components/NotificationBell.vue";
import UiButton from "@/shared/ui/Button.vue";
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand" to="/" aria-label="平行线首页">
        <span class="brand-mark">平</span>
        <span>
          <strong>平行线</strong>
          <small>冷静的技术社区</small>
        </span>
      </RouterLink>

      <nav class="nav-links" aria-label="主导航">
        <RouterLink to="/">最新</RouterLink>
        <a href="#top">热榜</a>
        <a href="#boards">版块</a>
        <a href="#hot">热门</a>
        <a href="#votes">投票</a>
      </nav>

      <a-input
        class="search-box"
        placeholder="搜索主题、标签、作者"
        aria-label="搜索平行线"
      >
        <template #prefix>
          <SearchOutlined />
        </template>
      </a-input>

      <div class="topbar-actions">
        <NotificationBell :count="3">
          <BellOutlined />
        </NotificationBell>
        <UiButton tone="primary" aria-label="发布主题">
          <template #icon>
            <PlusOutlined />
          </template>
          <span class="publish-label">发布主题</span>
        </UiButton>
      </div>
    </header>

    <main class="shell-main">
      <slot />
    </main>
  </div>
</template>

<style scoped lang="scss" src="./AppShell.scss"></style>
