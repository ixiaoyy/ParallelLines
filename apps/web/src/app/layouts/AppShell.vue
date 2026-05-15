<script setup lang="ts">
import { PlusOutlined, SearchOutlined } from "@ant-design/icons-vue";
import { ref } from "vue";
import { useRouter } from "vue-router";

import NotificationBell from "@/features/notifications/components/NotificationBell.vue";
import UiButton from "@/shared/ui/Button.vue";

const router = useRouter();
const globalSearch = ref("");

function submitGlobalSearch() {
  const q = globalSearch.value.trim();
  if (!q) {
    return;
  }

  void router.push({ name: "search", query: { q } });
}
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
        <RouterLink :to="{ name: 'admin-moderation' }">审核</RouterLink>
      </nav>

      <a-input
        class="search-box"
        v-model:value="globalSearch"
        placeholder="搜索主题、标签、作者"
        aria-label="搜索平行线"
        @press-enter="submitGlobalSearch"
      >
        <template #prefix>
          <SearchOutlined />
        </template>
      </a-input>

      <div class="topbar-actions">
        <NotificationBell />
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
