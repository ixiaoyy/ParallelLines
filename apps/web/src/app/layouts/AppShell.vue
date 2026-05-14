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
        <RouterLink :to="{ name: 'home', hash: '#hot' }">热榜</RouterLink>
        <RouterLink to="/boards">版块</RouterLink>
        <RouterLink :to="{ name: 'home', hash: '#solved' }">优质</RouterLink>
        <RouterLink :to="{ name: 'home', hash: '#votes' }">投票</RouterLink>
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
        <RouterLink class="publish-link" :to="{ name: 'new-topic' }" aria-label="发布主题">
          <UiButton tone="primary">
            <template #icon>
              <PlusOutlined />
            </template>
            <span class="publish-label">发布主题</span>
          </UiButton>
        </RouterLink>
      </div>
    </header>

    <main class="shell-main">
      <slot />
    </main>
  </div>
</template>

<style scoped lang="scss" src="./AppShell.scss"></style>
