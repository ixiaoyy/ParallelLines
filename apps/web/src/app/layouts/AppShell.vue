<script setup lang="ts">
import {
  CloseOutlined,
  DownOutlined,
  EnterOutlined,
  MenuOutlined,
  PlusOutlined,
  SearchOutlined,
} from "@ant-design/icons-vue";
import { computed, ref, watch, watchEffect } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { RouteLocationRaw } from "vue-router";

import { publicSettingString, siteText } from "@/features/admin/model";
import { usePublicSiteSettings } from "@/features/admin/queries";
import type { UserPublic } from "@/features/auth/model";
import { canAccessModeration, isAdmin } from "@/features/auth/permissions";
import { useCurrentUser, useLogout } from "@/features/auth/queries";
import NotificationBell from "@/features/notifications/components/NotificationBell.vue";
import PluginSlot from "@/features/plugins/components/PluginSlot.vue";
import { useLocale } from "@/shared/i18n/locale";
import { useOutsidePointerDown } from "@/shared/lib/useOutsidePointerDown";
import UiButton from "@/shared/ui/Button.vue";
import { applySiteBranding } from "@/shared/theme/siteBranding";

const router = useRouter();
const route = useRoute();
const globalSearch = ref("");
const isNavOpen = ref(false);
const topbarRef = ref<HTMLElement | null>(null);
const accountMenuRef = ref<HTMLDetailsElement | null>(null);
const currentUserQuery = useCurrentUser();
const siteSettingsQuery = usePublicSiteSettings();
const logout = useLogout();
const { locale } = useLocale();
let profileRoutePrefetched = false;
let adminRoutePrefetched = false;
let moderationRoutePrefetched = false;
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
const brandHomeLabel = computed(() => t("brand.home_aria", "返回首页"));
const adminLinkTarget = computed<RouteLocationRaw>(() =>
  isAdmin(currentUser.value) ? { name: "admin-dashboard" } : { name: "admin-moderation" },
);
const adminLinkLabel = computed(() =>
  isAdmin(currentUser.value) ? t("nav.admin", "后台") : t("nav.moderation", "审核"),
);
const canSubmitGlobalSearch = computed(() => Boolean(globalSearch.value.trim()));
const isCurrentUserProfileActive = computed(() => {
  if (!currentUser.value) {
    return false;
  }

  return (
    route.name === "my-profile" ||
    (route.name === "user-profile" && String(route.params.username ?? "") === currentUser.value.username)
  );
});

interface NavItem {
  key:
    | "home"
    | "boards"
    | "users"
    | "security"
    | "email"
    | "messages"
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
    closeAccountMenu();
  },
);

watch(
  currentUser,
  (user) => {
    if (user) {
      scheduleAccountRoutePrefetch(user);
    }
  },
  { immediate: true },
);

useOutsidePointerDown(topbarRef, closeNavigation, () => isNavOpen.value);
useOutsidePointerDown(accountMenuRef, closeAccountMenu, () => Boolean(accountMenuRef.value?.open));

async function handleLogout() {
  closeAccountMenu();
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

function closeAccountMenu() {
  if (accountMenuRef.value) {
    accountMenuRef.value.open = false;
  }
}

function scheduleAccountRoutePrefetch(user: UserPublic) {
  scheduleIdleTask(() => {
    if (!profileRoutePrefetched) {
      profileRoutePrefetched = true;
      void import("@/pages/user/UserProfilePage.vue");
    }

    if (isAdmin(user) && !adminRoutePrefetched) {
      adminRoutePrefetched = true;
      void import("@/pages/admin/AdminDashboardPage.vue");
      return;
    }

    if (canAccessModeration(user) && !moderationRoutePrefetched) {
      moderationRoutePrefetched = true;
      void import("@/pages/admin/ModerationPage.vue");
    }
  });
}

function scheduleIdleTask(callback: () => void) {
  if (window.requestIdleCallback) {
    window.requestIdleCallback(callback, { timeout: 2_000 });
    return;
  }

  window.setTimeout(callback, 400);
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
    <header ref="topbarRef" class="topbar" @keydown.esc="closeNavigation">
      <RouterLink class="brand" :to="{ name: 'home' }" :aria-label="brandHomeLabel" :title="brandHomeLabel">
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
            :aria-label="t('search.submit_aria', '按回车搜索')"
            :title="t('search.submit_aria', '按回车搜索')"
            @click="submitGlobalSearch"
          >
            <EnterOutlined />
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
        <PluginSlot class="desktop-plugin-slot" slot-name="app.nav" />

        <NotificationBell v-if="currentUser" class="topbar-notification" />

        <RouterLink v-if="!currentUser" class="auth-link auth-link--guest" :to="{ name: 'auth' }">
          {{ t("auth.login_register", "登录/注册") }}
        </RouterLink>
        <template v-else>
          <details ref="accountMenuRef" class="account-menu" @keydown.esc="closeAccountMenu">
            <summary
              class="account-menu__summary"
              :class="{ 'is-active': isCurrentUserProfileActive }"
              :aria-label="t('nav.account_menu', '打开账号菜单')"
            >
              <span>
                <strong>{{ t("nav.profile", "个人中心") }}</strong>
                <small>@{{ currentUser.username }}</small>
              </span>
              <DownOutlined class="account-menu__chevron" />
            </summary>
            <div class="account-menu__panel">
              <RouterLink
                class="account-menu__item account-menu__item--profile"
                :to="{ name: 'my-profile' }"
                :class="{ 'is-active': isCurrentUserProfileActive }"
                @click="closeAccountMenu"
              >
                <span>{{ t("nav.profile", "个人中心") }}</span>
                <small>{{ currentUser.points_balance }} 可用积分</small>
              </RouterLink>
              <RouterLink
                v-if="canAccessModeration(currentUser)"
                class="account-menu__item"
                :to="adminLinkTarget"
                :class="{ 'is-active': route.name === 'admin-dashboard' || route.name === 'admin-moderation' }"
                @click="closeAccountMenu"
              >
                {{ adminLinkLabel }}
              </RouterLink>
              <RouterLink
                class="account-menu__item"
                :to="{ name: 'security' }"
                :class="{ 'is-active': route.name === 'security' }"
                @click="closeAccountMenu"
              >
                {{ t("nav.security", "账号安全") }}
              </RouterLink>
              <RouterLink
                class="account-menu__item"
                :to="{ name: 'email-preferences' }"
                :class="{ 'is-active': route.name === 'email-preferences' }"
                @click="closeAccountMenu"
              >
                {{ t("nav.email", "邮件偏好") }}
              </RouterLink>
              <RouterLink
                class="account-menu__item"
                :to="{ name: 'messages' }"
                :class="{ 'is-active': route.name === 'messages' }"
                @click="closeAccountMenu"
              >
                {{ t("nav.messages", "私信") }}
              </RouterLink>
              <RouterLink
                class="account-menu__item"
                :to="{ name: 'events' }"
                :class="{ 'is-active': route.name === 'events' }"
                @click="closeAccountMenu"
              >
                {{ t("nav.events", "活动") }}
              </RouterLink>
              <RouterLink
                class="account-menu__item"
                :to="{ name: 'my-reviewables' }"
                :class="{ 'is-active': route.name === 'my-reviewables' }"
                @click="closeAccountMenu"
              >
                {{ t("nav.reviewables", "申诉") }}
              </RouterLink>
              <button class="account-menu__item account-menu__item--danger" type="button" @click="handleLogout">
                {{ t("auth.logout", "退出") }}
              </button>
            </div>
          </details>
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
              :aria-label="t('search.submit_aria', '按回车搜索')"
              :title="t('search.submit_aria', '按回车搜索')"
              @click="submitGlobalSearch"
            >
              <EnterOutlined />
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

