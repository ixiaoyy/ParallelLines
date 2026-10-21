<script setup lang="ts">
import { ToolOutlined } from "@ant-design/icons-vue";

import SiteNavigation from "@/shared/ui/SiteNavigation.vue";
</script>

<template>
  <div class="tools-shell">
    <header class="tools-site-header">
      <RouterLink class="tools-site-brand" :to="{ name: 'home' }" aria-label="平行线首页">
        <img src="/logo-lines-mark.png" alt="" width="48" height="42" />
        <strong>平行线</strong>
      </RouterLink>
    </header>
    <main class="tools-page" aria-labelledby="tools-page-title">
      <header class="tools-page__header">
        <span><ToolOutlined aria-hidden="true" /> 工具</span>
        <h1 id="tools-page-title">工具</h1>
      </header>
      <section class="tools-page__empty" aria-labelledby="tools-empty-title">
        <ToolOutlined aria-hidden="true" />
        <h2 id="tools-empty-title">暂无可用工具</h2>
        <p>工具开放后会显示在这里。</p>
        <RouterLink :to="{ name: 'home' }">去看看游戏</RouterLink>
      </section>
    </main>
    <footer class="tools-site-footer"><SiteNavigation /></footer>
  </div>
</template>

<style scoped lang="scss" src="./ToolsPage.scss"></style>
