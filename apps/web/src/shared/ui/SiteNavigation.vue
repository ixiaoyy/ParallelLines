<script setup lang="ts">
import { useRoute } from "vue-router";

import { IS_FORUM_SITE, SITE_LINKS } from "@/shared/site/links";

withDefaults(defineProps<{ tone?: "default" | "catalog" }>(), { tone: "default" });
// 产品间使用完整地址，论坛构建中的游戏入口不能误指向当前论坛首页。
const route = useRoute();
</script>

<template>
  <nav class="site-navigation" :class="`site-navigation--${tone}`" aria-label="页脚导航">
    <a v-if="IS_FORUM_SITE" :href="SITE_LINKS.games">游戏</a>
    <RouterLink v-else :to="{ name: 'home' }" exact-active-class="is-active">游戏</RouterLink>
    <span aria-hidden="true">|</span>
    <RouterLink v-if="IS_FORUM_SITE" :to="{ name: 'forum-home' }" class="is-active" :aria-current="route.name === 'forum-home' ? 'page' : undefined">圈子</RouterLink>
    <a v-else :href="SITE_LINKS.forum">圈子</a>
    <span aria-hidden="true">|</span>
    <a :href="SITE_LINKS.tools" :class="{ 'is-active': route.name === 'tools' }" :aria-current="route.name === 'tools' ? 'page' : undefined">工具</a>
    <span aria-hidden="true">|</span>
    <a :href="SITE_LINKS.chat">聊天</a>
  </nav>
</template>

<style scoped lang="scss">
.site-navigation { display: inline-flex; align-items: center; gap: 8px; color: var(--text); font-size: 14px; white-space: nowrap; }
.site-navigation a { display: inline-flex; min-width: 44px; min-height: 44px; align-items: center; justify-content: center; border: 0; padding: 0; color: inherit; background: transparent; font: inherit; text-decoration: none; }
.site-navigation a:hover { text-decoration: underline; }
.site-navigation a:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 3px; }
.site-navigation a.is-active { font-weight: 700; }
.site-navigation--catalog { color: #3adeff; font-family: var(--catalog-font); }
</style>
