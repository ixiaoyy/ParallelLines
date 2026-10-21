<script setup lang="ts">
withDefaults(defineProps<{ tone?: "default" | "catalog" }>(), { tone: "default" });
</script>

<template>
  <nav class="site-navigation" :class="`site-navigation--${tone}`" aria-label="页脚导航">
    <RouterLink :to="{ name: 'home' }" exact-active-class="is-active">游戏</RouterLink>
    <span aria-hidden="true">|</span>
    <button type="button" disabled title="圈子暂未开放" aria-label="圈子，暂未开放">圈子</button>
    <span aria-hidden="true">|</span>
    <RouterLink :to="{ name: 'tools' }" exact-active-class="is-active">工具</RouterLink>
  </nav>
</template>

<style scoped lang="scss">
.site-navigation { display: inline-flex; align-items: center; gap: 8px; color: var(--text); font-size: 14px; white-space: nowrap; }
.site-navigation a, .site-navigation button { display: inline-flex; min-height: 44px; align-items: center; border: 0; padding: 0; color: inherit; background: transparent; font: inherit; text-decoration: none; }
.site-navigation a:hover { text-decoration: underline; }
.site-navigation a:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 3px; }
.site-navigation a.is-active { font-weight: 700; }
.site-navigation button:disabled { color: var(--muted); cursor: not-allowed; }
.site-navigation--catalog { color: #3adeff; font-family: var(--catalog-font); }
.site-navigation--catalog button:disabled { color: #94adc7; }
</style>
