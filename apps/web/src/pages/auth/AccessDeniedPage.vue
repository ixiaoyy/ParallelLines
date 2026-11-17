<script setup lang="ts">
import { uiText } from "@/shared/i18n/locale";
import LanguageSwitcher from "@/shared/ui/LanguageSwitcher.vue";
import { computed } from "vue";
import { useRoute } from "vue-router";

import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const route = useRoute();
const requiredAccess = computed(() => String(route.query.required ?? ""));
const deniedCopy = computed(() => {
  if (requiredAccess.value === "admin") {
    return {
      title: "需要管理员权限",
      description: "当前账号不能进入站点后台。你仍然可以浏览公开版块、发布主题或回到个人中心。",
    };
  }
  if (requiredAccess.value === "moderation") {
    return {
      title: "需要审核权限",
      description: "当前账号不能进入审核后台。普通用户的审核申诉与处理记录在「我的审核」中查看。",
    };
  }

  return {
    title: "没有访问权限",
    description: "当前账号不能打开这个页面。请确认登录账号或返回公开页面继续浏览。",
  };
});
</script>

<template>
  <main class="access-denied-page" aria-labelledby="access-denied-title"><LanguageSwitcher style="position: fixed; top: 12px; right: 16px; z-index: 40" />
    <UiCard class="access-denied-card">
      <span class="access-denied-card__eyebrow">{{ uiText("访问受限") }}</span>
      <h1 id="access-denied-title">{{ uiText(deniedCopy.title) }}</h1>
      <p>{{ uiText(deniedCopy.description) }}</p>
      <div class="access-denied-card__actions">
        <RouterLink :to="{ name: 'forum-home' }">
          <UiButton tone="primary">{{ uiText("返回首页") }}</UiButton>
        </RouterLink>
        <RouterLink v-if="requiredAccess === 'moderation'" :to="{ name: 'my-reviewables' }">
          <UiButton tone="subtle">{{ uiText("我的审核") }}</UiButton>
        </RouterLink>
        <RouterLink :to="{ name: 'account-home' }">
          <UiButton tone="ghost">{{ uiText("个人中心") }}</UiButton>
        </RouterLink>
      </div>
    </UiCard>
  </main>
</template>

<style scoped lang="scss" src="./AccessDeniedPage.scss"></style>
