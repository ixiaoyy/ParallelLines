<script setup lang="ts">
import { CloseOutlined, MenuOutlined, PlusOutlined, SearchOutlined } from "@ant-design/icons-vue";
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { RouteLocationRaw } from "vue-router";

import { publicSettingString } from "@/features/admin/model";
import { usePublicSiteSettings } from "@/features/admin/queries";
import { canAccessModeration, isAdmin } from "@/features/auth/permissions";
import { useCurrentUser, useLogout } from "@/features/auth/queries";
import NotificationBell from "@/features/notifications/components/NotificationBell.vue";
import UiButton from "@/shared/ui/Button.vue";

const router = useRouter();
const route = useRoute();
const globalSearch = ref("");
const isNavOpen = ref(false);
const currentUserQuery = useCurrentUser();
const siteSettingsQuery = usePublicSiteSettings();
const logout = useLogout();
const currentUser = computed(() => currentUserQuery.data.value);
const siteTitle = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "site_title", "平行线"),
);
const siteTagline = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "site_tagline", "让答案可追溯"),
);
const adminLinkTarget = computed<RouteLocationRaw>(() =>
  isAdmin(currentUser.value) ? { name: "admin-dashboard" } : { name: "admin-moderation" },
);
const adminLinkLabel = computed(() => (isAdmin(currentUser.value) ? "后台" : "审核"));

interface NavItem {
  key: "home" | "boards" | "security" | "email" | "admin" | "moderation";
  label: string;
  to: RouteLocationRaw;
}

const navItems: NavItem[] = [
  { key: "home", label: "首页", to: "/" },
  { key: "boards", label: "版块", to: "/boards" },
  { key: "security", label: "安全", to: { name: "security" } },
  { key: "email", label: "邮件", to: { name: "email-preferences" } },
  { key: "admin", label: "后台", to: { name: "admin-dashboard" } },
  { key: "moderation", label: "审核", to: { name: "admin-moderation" } },
];

const visibleNavItems = computed(() =>
  navItems.filter((item) => {
    if (item.key === "security") {
      return Boolean(currentUser.value);
    }

    if (item.key === "email") {
      return Boolean(currentUser.value);
    }

    if (item.key === "admin") {
      return isAdmin(currentUser.value);
    }

    return item.key !== "moderation" || canAccessModeration(currentUser.value);
  }),
);

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

function isNavItemActive(item: NavItem) {
  if (item.key === "home") {
    return route.name === "home";
  }

  if (item.key === "boards") {
    return route.name === "board-directory" || route.name === "board-detail";
  }

  if (item.key === "security") {
    return route.name === "security";
  }

  if (item.key === "email") {
    return route.name === "email-preferences";
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
      <RouterLink class="brand" to="/" aria-label="平行线首页">
        <span class="brand-mark">
          <img class="brand-logo" src="/logo-lines.png" alt="" aria-hidden="true" />
        </span>
        <span>
          <strong>{{ siteTitle }}</strong>
          <small>{{ siteTagline }}</small>
        </span>
      </RouterLink>

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

      <button
        class="nav-toggle"
        type="button"
        :aria-expanded="isNavOpen"
        aria-controls="mobile-navigation"
        :aria-label="isNavOpen ? '收起导航' : '展开导航'"
        @click="toggleNavigation"
      >
        <CloseOutlined v-if="isNavOpen" />
        <MenuOutlined v-else />
        <span>{{ isNavOpen ? "收起" : "导航" }}</span>
      </button>

      <div class="topbar-actions">
        <RouterLink
          v-if="canAccessModeration(currentUser)"
          class="admin-link"
          :to="adminLinkTarget"
          :class="{ 'is-active': route.name === 'admin-dashboard' || route.name === 'admin-moderation' }"
        >
          {{ adminLinkLabel }}
        </RouterLink>

        <NotificationBell />

        <RouterLink v-if="!currentUser" class="auth-link" :to="{ name: 'auth' }">登录/注册</RouterLink>
        <template v-else>
          <RouterLink class="auth-link" :to="{ name: 'security' }" :class="{ 'is-active': route.name === 'security' }">
            安全
          </RouterLink>
          <RouterLink
            class="auth-link"
            :to="{ name: 'email-preferences' }"
            :class="{ 'is-active': route.name === 'email-preferences' }"
          >
            邮件
          </RouterLink>
          <RouterLink class="user-link" :to="{ name: 'user-profile', params: { username: currentUser.username } }">
            {{ currentUser.username }}
          </RouterLink>
          <button class="logout-button" type="button" @click="handleLogout">退出</button>
        </template>
        <RouterLink class="publish-link" :to="{ name: 'new-topic' }" aria-label="发布主题">
          <UiButton tone="primary">
            <template #icon>
              <PlusOutlined />
            </template>
            <span class="publish-label">发布主题</span>
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
        </nav>

        <a-input
          v-model:value="globalSearch"
          class="mobile-search-box"
          placeholder="搜索主题、标签、作者"
          aria-label="移动端搜索平行线"
          @press-enter="submitGlobalSearch"
        >
          <template #prefix>
            <SearchOutlined />
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

