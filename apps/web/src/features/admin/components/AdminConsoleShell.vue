<script setup lang="ts">
import {
  AppstoreOutlined,
  BarChartOutlined,
  CloseOutlined,
  ExportOutlined,
  MenuOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  UserOutlined,
} from "@ant-design/icons-vue";
import { computed, defineAsyncComponent, nextTick, ref, watch } from "vue";
import { useRoute } from "vue-router";
import type { Component } from "vue";

import { adminRoleLabel, publicSettingString, siteText } from "@/features/admin/model";
import { usePublicSiteSettings } from "@/features/admin/queries";
import { isAdmin } from "@/features/auth/permissions";
import { useCurrentUser } from "@/features/auth/queries";
import { useMediaQuery } from "@/shared/lib/useMediaQuery";

// Loads notification behavior only when the operations console is rendered.
// No parameters; return value is the async notification component and the side effect is chunk loading on demand.
const NotificationBell = defineAsyncComponent(() =>
  import("@/features/notifications/components/NotificationBell.vue"),
);

interface AdminNavigationItem {
  id: "dashboard" | "analytics" | "users" | "moderation" | "system";
  label: string;
  mobileLabel: string;
  path: string;
  icon: Component;
  adminOnly: boolean;
}

const route = useRoute();
const isDrawerOpen = ref(false);
const sidebarElement = ref<HTMLElement | null>(null);
const menuButtonElement = ref<HTMLButtonElement | null>(null);
const drawerCloseButtonElement = ref<HTMLButtonElement | null>(null);
const isCompactViewport = useMediaQuery("(max-width: 860px)", false);
const currentUserQuery = useCurrentUser();
const siteSettingsQuery = usePublicSiteSettings();
const currentUser = computed(() => currentUserQuery.data.value);
const DEFAULT_BRAND_LOGO_URL = "/logo-lines-mark.png";
const LEGACY_BRAND_LOGO_URLS = new Set(["/logo-lines.png", "/favicon.svg"]);

// Resolves an admin-shell label through the existing site-text override system.
// `key` is the stable translation key and `fallback` is the built-in Chinese copy; return value is display text with no side effects.
function t(key: string, fallback: string): string {
  return siteText(siteSettingsQuery.data.value, key, fallback);
}

const navigationItems = computed<AdminNavigationItem[]>(() => [
  {
    id: "dashboard",
    label: t("admin.nav.dashboard", "工作台"),
    mobileLabel: t("admin.nav.dashboard_short", "工作台"),
    path: "/admin",
    icon: AppstoreOutlined,
    adminOnly: true,
  },
  {
    id: "analytics",
    label: t("admin.nav.analytics", "访问与增长"),
    mobileLabel: t("admin.nav.analytics_short", "增长"),
    path: "/admin/analytics",
    icon: BarChartOutlined,
    adminOnly: true,
  },
  {
    id: "users",
    label: t("admin.nav.users", "用户管理"),
    mobileLabel: t("admin.nav.users_short", "用户"),
    path: "/admin/users",
    icon: UserOutlined,
    adminOnly: true,
  },
  {
    id: "moderation",
    label: t("admin.nav.moderation", "内容审核"),
    mobileLabel: t("admin.nav.moderation_short", "审核"),
    path: "/admin/moderation",
    icon: SafetyCertificateOutlined,
    adminOnly: false,
  },
  {
    id: "system",
    label: t("admin.nav.system", "系统运行"),
    mobileLabel: t("admin.nav.system_short", "系统"),
    path: "/admin/system",
    icon: SettingOutlined,
    adminOnly: true,
  },
]);

const visibleNavigationItems = computed(() =>
  navigationItems.value.filter((item) => !item.adminOnly || isAdmin(currentUser.value)),
);
const activeItem = computed(() => {
  const matchedItem = navigationItems.value.find((item) => item.path === route.path);
  return matchedItem ?? navigationItems.value[0];
});
const adminName = computed(() =>
  currentUser.value?.display_name?.trim() || currentUser.value?.username || t("admin.user.fallback", "管理员"),
);
const adminRole = computed(() => adminRoleLabel(currentUser.value?.role ?? "admin"));
const adminAvatarUrl = computed(() => currentUser.value?.avatar_url?.trim() || "");
const consoleTitle = computed(() => t("admin.console.title", "运营控制台"));
const siteTitle = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "site_title", "平行线"),
);
const backendBrandLabel = computed(() => `${siteTitle.value}后台`);
// Keeps the console aligned with runtime branding while preserving the protected official logo fallback.
// No parameters; return value is a safe configured logo URL. Side effect: none.
const brandLogoUrl = computed(() => {
  const configuredLogo = publicSettingString(
    siteSettingsQuery.data.value,
    "brand_logo_url",
    DEFAULT_BRAND_LOGO_URL,
  );
  return LEGACY_BRAND_LOGO_URLS.has(configuredLogo) ? DEFAULT_BRAND_LOGO_URL : configuredLogo;
});

// Closes the compact navigation drawer and optionally restores focus to its trigger.
// Key parameter `restoreFocus` controls focus restoration; return value is none. Side effect: updates drawer state and focus.
function closeDrawer(restoreFocus = true): void {
  isDrawerOpen.value = false;
  if (restoreFocus && isCompactViewport.value) {
    void nextTick(() => menuButtonElement.value?.focus({ preventScroll: true }));
  }
}

// Opens the compact navigation drawer and moves keyboard focus inside it.
// No parameters or return value; side effect updates drawer state and focuses the close control.
function openDrawer(): void {
  isDrawerOpen.value = true;
  void nextTick(() => drawerCloseButtonElement.value?.focus({ preventScroll: true }));
}

// Keeps Tab navigation inside the open compact drawer while the workspace is inert.
// Key parameter `event` is a sidebar keyboard event; return value is none. Side effect: may wrap keyboard focus.
function trapDrawerFocus(event: KeyboardEvent): void {
  if (event.key !== "Tab" || !isCompactViewport.value || !isDrawerOpen.value) {
    return;
  }
  const focusableElements = Array.from(
    sidebarElement.value?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ) ?? [],
  ).filter((element) => element.offsetParent !== null);
  const firstElement = focusableElements[0];
  const lastElement = focusableElements.at(-1);
  if (!firstElement || !lastElement) {
    return;
  }
  if (event.shiftKey && document.activeElement === firstElement) {
    event.preventDefault();
    lastElement.focus();
  } else if (!event.shiftKey && document.activeElement === lastElement) {
    event.preventDefault();
    firstElement.focus();
  }
}

watch(
  () => route.fullPath,
  () => closeDrawer(false),
);
</script>

<template>
  <div
    class="admin-console-shell"
    :class="{ 'is-drawer-open': isDrawerOpen }"
    @keydown.esc="closeDrawer()"
  >
    <aside
      ref="sidebarElement"
      id="admin-console-navigation"
      class="admin-console-shell__sidebar"
      :aria-hidden="isCompactViewport && !isDrawerOpen ? 'true' : undefined"
      :inert="isCompactViewport && !isDrawerOpen"
      @keydown="trapDrawerFocus"
    >
      <RouterLink class="admin-console-shell__brand" to="/" :aria-label="`返回${siteTitle}首页`">
        <img :src="brandLogoUrl" alt="" />
        <strong>{{ backendBrandLabel }}</strong>
      </RouterLink>

      <button
        ref="drawerCloseButtonElement"
        class="admin-console-shell__drawer-close"
        type="button"
        aria-label="关闭后台导航"
        @click="closeDrawer()"
      >
        <CloseOutlined />
      </button>

      <nav class="admin-console-shell__nav" aria-label="后台主导航">
        <RouterLink
          v-for="item in visibleNavigationItems"
          :key="item.id"
          class="admin-console-shell__nav-item"
          :to="item.path"
          :aria-current="item.id === activeItem.id ? 'page' : undefined"
          :class="{ 'is-active': item.id === activeItem.id }"
          @click="closeDrawer()"
        >
          <component :is="item.icon" aria-hidden="true" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="admin-console-shell__sidebar-footer">
        <RouterLink class="admin-console-shell__return" to="/">
          <ExportOutlined aria-hidden="true" />
          <span>返回站点</span>
        </RouterLink>

        <RouterLink class="admin-console-shell__admin-card" :to="{ name: 'account-home' }">
          <span class="admin-console-shell__avatar" aria-hidden="true">
            <img v-if="adminAvatarUrl" :src="adminAvatarUrl" alt="" />
            <UserOutlined v-else />
          </span>
          <span class="admin-console-shell__admin-copy">
            <strong>{{ adminName }}</strong>
            <small>{{ adminRole }}</small>
          </span>
        </RouterLink>
      </div>
    </aside>

    <button
      class="admin-console-shell__scrim"
      type="button"
      aria-label="关闭后台导航"
      :tabindex="isDrawerOpen ? 0 : -1"
      @click="closeDrawer()"
    />

    <div
      class="admin-console-shell__workspace"
      :aria-hidden="isCompactViewport && isDrawerOpen ? 'true' : undefined"
      :inert="isCompactViewport && isDrawerOpen"
    >
      <header class="admin-console-shell__topbar">
        <div class="admin-console-shell__topbar-start">
          <button
            ref="menuButtonElement"
            class="admin-console-shell__menu-button"
            type="button"
            aria-label="打开后台导航"
            aria-controls="admin-console-navigation"
            :aria-expanded="isDrawerOpen"
            @click="openDrawer"
          >
            <MenuOutlined />
          </button>

          <div class="admin-console-shell__mobile-brand" aria-hidden="true">
            <img :src="brandLogoUrl" alt="" />
            <strong>{{ backendBrandLabel }}</strong>
          </div>

          <div class="admin-console-shell__breadcrumb" aria-label="当前位置">
            <span>{{ consoleTitle }}</span>
            <span aria-hidden="true">/</span>
            <strong>{{ activeItem.label }}</strong>
          </div>
        </div>

        <div class="admin-console-shell__topbar-actions">
          <NotificationBell />
          <RouterLink class="admin-console-shell__topbar-user" :to="{ name: 'account-home' }">
            <span class="admin-console-shell__avatar admin-console-shell__avatar--small" aria-hidden="true">
              <img v-if="adminAvatarUrl" :src="adminAvatarUrl" alt="" />
              <UserOutlined v-else />
            </span>
            <span>{{ adminName }}</span>
          </RouterLink>
        </div>
      </header>

      <main class="admin-console-shell__content">
        <slot />
      </main>
    </div>

    <nav
      class="admin-console-shell__bottom-nav"
      aria-label="移动端后台主导航"
      :aria-hidden="isCompactViewport && isDrawerOpen ? 'true' : undefined"
      :inert="isCompactViewport && isDrawerOpen"
      :style="{ '--admin-navigation-count': visibleNavigationItems.length }"
    >
      <RouterLink
        v-for="item in visibleNavigationItems"
        :key="item.id"
        class="admin-console-shell__bottom-item"
        :to="item.path"
        :aria-current="item.id === activeItem.id ? 'page' : undefined"
        :class="{ 'is-active': item.id === activeItem.id }"
      >
        <component :is="item.icon" aria-hidden="true" />
        <small>{{ item.mobileLabel }}</small>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped lang="scss" src="./AdminConsoleShell.scss"></style>
