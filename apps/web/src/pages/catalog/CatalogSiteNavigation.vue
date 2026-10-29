<script setup lang="ts">
import { AppstoreOutlined, TeamOutlined, ToolOutlined } from "@ant-design/icons-vue";
</script>

<template>
  <nav class="catalog-site-navigation" aria-label="站点导航">
    <RouterLink :to="{ name: 'home' }" exact-active-class="is-active"><AppstoreOutlined aria-hidden="true" />游戏</RouterLink>
    <button type="button" disabled title="圈子暂未开放" aria-label="圈子，暂未开放"><TeamOutlined aria-hidden="true" />圈子</button>
    <RouterLink :to="{ name: 'tools' }" exact-active-class="is-active"><ToolOutlined aria-hidden="true" />工具</RouterLink>
  </nav>
</template>

<style scoped lang="scss">
.catalog-site-navigation { display: inline-flex; flex: 0 0 auto; align-items: center; gap: 4px; color: var(--catalog-ink); font: 700 15px var(--catalog-font); white-space: nowrap; }
.catalog-site-navigation a, .catalog-site-navigation button { display: inline-flex; min-height: 44px; align-items: center; justify-content: center; gap: 6px; border: 0; border-radius: 8px; padding: 0 12px; color: inherit; background: transparent; font: inherit; text-decoration: none; }
.catalog-site-navigation .anticon { font-size: 19px; }
.catalog-site-navigation a:hover { background: #dce5dc; }
.catalog-site-navigation a.is-active { color: #fff; background: var(--catalog-jade); }
.catalog-site-navigation a:focus-visible { outline: 2px solid var(--catalog-focus); outline-offset: 3px; }
.catalog-site-navigation button:disabled { color: #64766d; cursor: not-allowed; }
@media (max-width: 760px) {
  .catalog-site-navigation { margin-left: auto; font-size: 13px; }
  .catalog-site-navigation a, .catalog-site-navigation button { gap: 4px; padding-inline: 7px; }
  .catalog-site-navigation .anticon { font-size: 17px; }
}
</style>
