<script setup lang="ts">
import { SITE_LINKS } from "@/shared/site/links";

import CatalogIcon from "./CatalogIcon.vue";
</script>

<template>
  <nav class="catalog-site-navigation" aria-label="站点导航">
    <RouterLink :to="{ name: 'home' }" exact-active-class="is-active"><CatalogIcon name="game" />游戏</RouterLink>
    <a :href="SITE_LINKS.forum"><CatalogIcon name="circle" />圈子</a>
    <a :href="SITE_LINKS.tools"><CatalogIcon name="tools" />工具</a>
    <a :href="SITE_LINKS.chat">聊天</a>
  </nav>
</template>

<style scoped lang="scss">
.catalog-site-navigation { display: inline-flex; flex: 0 0 auto; align-items: center; gap: 2px; color: #796c85; font: 700 16px var(--catalog-heading-font, var(--catalog-font)); white-space: nowrap; }
.catalog-site-navigation a { display: inline-flex; min-width: 44px; min-height: 44px; align-items: center; justify-content: center; border: 0; border-radius: 10px; padding: 0 8px; color: inherit; background: transparent; font: inherit; text-decoration: none; }
.catalog-site-navigation :deep(.catalog-icon) { display: none; }
.catalog-site-navigation a:hover { background: #f1eff4; }
.catalog-site-navigation a.is-active { color: #65546f; background: transparent; }
.catalog-site-navigation a:focus-visible { outline: 2px solid var(--catalog-focus); outline-offset: 3px; }
@media (max-width: 760px) {
  .catalog-site-navigation { margin-left: auto; gap: 2px; font-size: 13px; }
  .catalog-site-navigation a { min-height: 44px; padding-inline: 6px; }
}
@media (max-width: 359px) {
  .catalog-site-navigation { font-size: 12px; }
  .catalog-site-navigation a { padding-inline: 4px; }
}
</style>
