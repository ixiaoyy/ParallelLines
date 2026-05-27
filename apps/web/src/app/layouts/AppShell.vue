<script setup lang="ts">
import { CloseOutlined, MenuOutlined, PlusOutlined, SearchOutlined } from "@ant-design/icons-vue";
import { computed, ref, watch, watchEffect } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { RouteLocationRaw } from "vue-router";

import { publicSettingString, siteText } from "@/features/admin/model";
import { usePublicSiteSettings } from "@/features/admin/queries";
import { canAccessModeration, isAdmin } from "@/features/auth/permissions";
import { useCurrentUser, useLogout } from "@/features/auth/queries";
import NotificationBell from "@/features/notifications/components/NotificationBell.vue";
import PluginSlot from "@/features/plugins/components/PluginSlot.vue";
import { useLocale } from "@/shared/i18n/locale";
import UiButton from "@/shared/ui/Button.vue";
import { applySiteBranding } from "@/shared/theme/siteBranding";

const router = useRouter();
const route = useRoute();
const globalSearch = ref("");
const isNavOpen = ref(false);
const currentUserQuery = useCurrentUser();
const siteSettingsQuery = usePublicSiteSettings();
const logout = useLogout();
const { locale } = useLocale();
const currentUser = computed(() => currentUserQuery.data.value);
const siteTitle = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "site_title", "平行线"),
);
const siteTagline = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "site_tagline", "让答案可追溯"),
);
const brandLogoUrl = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "brand_logo_url", "/logo-lines.png"),
);
const brandHomeLabel = computed(() => t("brand.home_aria", "平行线首页"));
const adminLinkTarget = computed<RouteLocationRaw>(() =>
  isAdmin(currentUser.value) ? { name: "admin-dashboard" } : { name: "admin-moderation" },
);
const adminLinkLabel = computed(() =>
  isAdmin(currentUser.value) ? t("nav.admin", "后台") : t("nav.moderation", "审核"),
);
const canSubmitGlobalSearch = computed(() => Boolean(globalSearch.value.trim()));

interface NavItem {
  key:
    | "home"
    | "boards"
    | "users"
    | "security"
    | "email"
    | "messages"
    | "chat"
    | "events"
    | "reviewables"
    | "admin"
    | "moderation";
  label: string;
  to: RouteLocationRaw;
}

const navItems = computed<NavItem[]>(() => [
  { key: "home", label: t("nav.home", "首页"), to: "/" },
  { key: "boards", label: t("nav.boards", "版块"), to: "/boards" },
  { key: "users", label: t("nav.users", "成员"), to: { name: "user-directory" } },
  { key: "security", label: t("nav.security", "安全"), to: { name: "security" } },
  { key: "email", label: t("nav.email", "邮件"), to: { name: "email-preferences" } },
  { key: "messages", label: t("nav.messages", "私信"), to: { name: "messages" } },
  { key: "chat", label: t("nav.chat", "Chat"), to: { name: "chat" } },
  { key: "events", label: t("nav.events", "活动"), to: { name: "events" } },
  { key: "reviewables", label: t("nav.reviewables", "申诉"), to: { name: "my-reviewables" } },
  { key: "admin", label: t("nav.admin", "后台"), to: { name: "admin-dashboard" } },
  { key: "moderation", label: t("nav.moderation", "审核"), to: { name: "admin-moderation" } },
]);

const visibleNavItems = computed(() =>
  navItems.value.filter((item) => {
    if (item.key === "security") {
      return Boolean(currentUser.value);
    }

    if (item.key === "email") {
      return Boolean(currentUser.value);
    }

    if (item.key === "messages") {
      return Boolean(currentUser.value);
    }

    if (item.key === "chat") {
      return Boolean(currentUser.value);
    }

    if (item.key === "reviewables") {
      return Boolean(currentUser.value);
    }

    if (item.key === "admin") {
      return isAdmin(currentUser.value);
    }

    return item.key !== "moderation" || canAccessModeration(currentUser.value);
  }),
);

watchEffect(() => {
  applySiteBranding(siteSettingsQuery.data.value?.settings);
});

watch(
  () => route.fullPath,
  () => {
    closeNavigation();
  },
);

async function handleLogout() {
  await logout();
}

function submitGlobalSearch() {
  const q = globalSearch.value.trim();
  if (!q) {
    return;
  }

  closeNavigation();
  void router.push({ name: "search", query: { q } });
}

function toggleNavigation() {
  isNavOpen.value = !isNavOpen.value;
}

function closeNavigation() {
  isNavOpen.value = false;
}

function t(key: string, fallback: string) {
  return siteText(siteSettingsQuery.data.value, key, fallback, locale.value);
}

function isNavItemActive(item: NavItem) {
  if (item.key === "home") {
    return route.name === "home";
  }

  if (item.key === "boards") {
    return route.name === "board-directory" || route.name === "board-detail";
  }

  if (item.key === "users") {
    return route.name === "user-directory" || route.name === "user-profile";
  }

  if (item.key === "security") {
    return route.name === "security";
  }

  if (item.key === "email") {
    return route.name === "email-preferences";
  }

  if (item.key === "messages") {
    return route.name === "messages";
  }

  if (item.key === "chat") {
    return route.name === "chat";
  }

  if (item.key === "events") {
    return route.name === "events";
  }

  if (item.key === "reviewables") {
    return route.name === "my-reviewables";
  }

  if (item.key === "admin") {
    return route.name === "admin-dashboard";
  }

  return route.name === "admin-moderation";
}
</script>



<template>
  <div class="app-shell">
    <header class="topbar">
      <RouterLink class="brand" to="/" :aria-label="brandHomeLabel">
        <span class="brand-mark">
          <img class="brand-logo" :src="brandLogoUrl" alt="" aria-hidden="true" />
        </span>
        <span>
          <strong>{{ siteTitle }}</strong>
          <small>{{ siteTagline }}</small>
        </span>
      </RouterLink>

      <a-input
        class="search-box"
        v-model:value="globalSearch"
        :placeholder="t('search.placeholder', '搜索主题、标签、作者')"
        :aria-label="t('search.aria', '搜索平行线')"
        @press-enter="submitGlobalSearch"
      >
        <template #prefix>
          <SearchOutlined />
        </template>
        <template #suffix>
          <button
            class="global-search-submit"
            type="button"
            :disabled="!canSubmitGlobalSearch"
            :aria-label="t('search.submit_aria', '搜索')"
            @click="submitGlobalSearch"
          >
            <SearchOutlined />
            <span class="global-search-submit__label">{{ t("search.submit", "搜索") }}</span>
          </button>
        </template>
      </a-input>

      <button
        class="nav-toggle"
        type="button"
        :aria-expanded="isNavOpen"
        aria-controls="mobile-navigation"
        :aria-label="isNavOpen ? t('nav.collapse_aria', '收起导航') : t('nav.expand_aria', '展开导航')"
        @click="toggleNavigation"
      >
        <CloseOutlined v-if="isNavOpen" />
        <MenuOutlined v-else />
        <span class="nav-toggle__label">{{ isNavOpen ? t("nav.collapse", "收起") : t("nav.menu", "导航") }}</span>
      </button>

      <div class="topbar-actions" :class="{ 'topbar-actions--guest': !currentUser }">
        <RouterLink
          v-if="canAccessModeration(currentUser)"
          class="admin-link"
          :to="adminLinkTarget"
          :class="{ 'is-active': route.name === 'admin-dashboard' || route.name === 'admin-moderation' }"
        >
          {{ adminLinkLabel }}
        </RouterLink>

        <PluginSlot class="desktop-plugin-slot" slot-name="app.nav" />

        <NotificationBell class="topbar-notification" />

        <RouterLink v-if="!currentUser" class="auth-link auth-link--guest" :to="{ name: 'auth' }">
          {{ t("auth.login_register", "登录/注册") }}
        </RouterLink>
        <template v-else>
          <RouterLink class="auth-link" :to="{ name: 'security' }" :class="{ 'is-active': route.name === 'security' }">
            {{ t("nav.security", "安全") }}
          </RouterLink>
          <RouterLink
            class="auth-link"
            :to="{ name: 'email-preferences' }"
            :class="{ 'is-active': route.name === 'email-preferences' }"
          >
            {{ t("nav.email", "邮件") }}
          </RouterLink>
          <RouterLink
            class="auth-link"
            :to="{ name: 'messages' }"
            :class="{ 'is-active': route.name === 'messages' }"
          >
            {{ t("nav.messages", "私信") }}
          </RouterLink>
          <RouterLink class="auth-link" :to="{ name: 'chat' }" :class="{ 'is-active': route.name === 'chat' }">
            {{ t("nav.chat", "Chat") }}
          </RouterLink>
          <RouterLink class="auth-link" :to="{ name: 'events' }" :class="{ 'is-active': route.name === 'events' }">
            {{ t("nav.events", "活动") }}
          </RouterLink>
          <RouterLink
            class="auth-link"
            :to="{ name: 'my-reviewables' }"
            :class="{ 'is-active': route.name === 'my-reviewables' }"
          >
            {{ t("nav.reviewables", "申诉") }}
          </RouterLink>
          <RouterLink class="user-link" :to="{ name: 'user-profile', params: { username: currentUser.username } }">
            <span class="user-link__name">{{ currentUser.username }}</span>
            <small>Lv.{{ currentUser.level }} · TL{{ currentUser.trust_level }} · {{ currentUser.points_balance }} 分</small>
          </RouterLink>
          <button class="logout-button" type="button" @click="handleLogout">
            {{ t("auth.logout", "退出") }}
          </button>
        </template>
        <RouterLink class="publish-link" :to="{ name: 'new-topic' }" :aria-label="t('topic.publish_aria', '发布主题')">
          <UiButton tone="primary">
            <template #icon>
              <PlusOutlined />
            </template>
            <span class="publish-label">{{ t("topic.publish", "发布主题") }}</span>
          </UiButton>
        </RouterLink>
      </div>

      <div v-show="isNavOpen" id="mobile-navigation" class="mobile-nav-panel">
        <nav class="mobile-nav-links" aria-label="移动主导航">
          <RouterLink
            v-for="item in visibleNavItems"
            :key="item.key"
            :to="item.to"
            :class="{ 'is-active': isNavItemActive(item) }"
            @click="closeNavigation"
          >
            {{ item.label }}
          </RouterLink>
          <PluginSlot slot-name="app.nav" compact />
        </nav>

        <a-input
          v-model:value="globalSearch"
          class="mobile-search-box"
          :placeholder="t('search.placeholder', '搜索主题、标签、作者')"
          :aria-label="t('search.mobile_aria', '移动端搜索平行线')"
          @press-enter="submitGlobalSearch"
        >
          <template #prefix>
            <SearchOutlined />
          </template>
          <template #suffix>
            <button
              class="global-search-submit"
              type="button"
              :disabled="!canSubmitGlobalSearch"
              :aria-label="t('search.submit_aria', '搜索')"
              @click="submitGlobalSearch"
            >
              <SearchOutlined />
              <span class="global-search-submit__label">{{ t("search.submit", "搜索") }}</span>
            </button>
          </template>
        </a-input>
      </div>
    </header>

    <main class="shell-main">
      <slot />
    </main>
  </div>
</template>

<style scoped lang="scss" src="./AppShell.scss"></style>

