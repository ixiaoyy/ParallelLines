<script setup lang="ts">
import {
  CloseOutlined,
  DownOutlined,
  EnterOutlined,
  MenuOutlined,
  PlusOutlined,
  SearchOutlined,
  ToolOutlined,
  UserOutlined,
} from "@ant-design/icons-vue";
import { computed, defineAsyncComponent, onUnmounted, ref, watch, watchEffect } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { RouteLocationRaw } from "vue-router";

import { publicSettingString, siteText } from "@/features/admin/model";
import { usePublicSiteSettings } from "@/features/admin/queries";
import type { UserPublic } from "@/features/auth/model";
import { canAccessModeration, isAdmin } from "@/features/auth/permissions";
import { useCurrentUser, useLogout } from "@/features/auth/queries";
import { useBoards } from "@/features/boards/queries";
import { useTags } from "@/features/tags/queries";
import { useLocale } from "@/shared/i18n/locale";
import { runWhenBrowserIdle } from "@/shared/lib/loadWhenIdle";
import { useMediaQuery } from "@/shared/lib/useMediaQuery";
import { useOutsidePointerDown } from "@/shared/lib/useOutsidePointerDown";
import { readRouteParam } from "@/shared/router/params";
import { resolveRouteSeoMeta, useSeoMeta } from "@/shared/seo/meta";
import UiButton from "@/shared/ui/Button.vue";
import { applySiteBranding } from "@/shared/theme/siteBranding";
import { setInterfaceTheme } from "@/shared/theme/interfaceTheme";

// Defers the notification widget so logged-in mobile first paint is not blocked by notification CSS/API setup.
// Key parameters: none. Return value is the NotificationBell component; side effect is idle-time chunk loading.
const NotificationBell = defineAsyncComponent(() =>
  runWhenBrowserIdle(2_000).then(() => import("@/features/notifications/components/NotificationBell.vue")),
);

// Keeps the administration shell out of the public-site bundle until an admin route is opened.
// No parameters; return value is the lazily loaded shell component and the side effect is chunk loading on demand.
const AdminConsoleShell = defineAsyncComponent(() =>
  import("@/features/admin/components/AdminConsoleShell.vue"),
);

// Loads optional plugin navigation only when the visible desktop bar needs it.
// Key parameters: none. Return value is the PluginSlot component; side effect is deferred chunk loading.
const PluginSlot = defineAsyncComponent(() => import("@/features/plugins/components/PluginSlot.vue"));

// Loads the desktop-style forum rail only after compact navigation is opened.
// Key parameters: none. Return value is the reusable forum navigation rail; side effect is deferred chunk loading.
const ForumLeftRail = defineAsyncComponent(() =>
  import("@/features/navigation/components/ForumLeftRail.vue"),
);

const router = useRouter();
const route = useRoute();
const globalSearch = ref("");
const isNavOpen = ref(false);
const isDesktopViewport = useMediaQuery("(min-width: 621px)", true);
const isMobileNavigationViewport = useMediaQuery("(max-width: 920px)", false);
// Mounts and fetches the compact forum rail only while its supported viewport menu is open.
// Parameters: none. Return value is the mobile navigation visibility flag; side effect: none.
const shouldShowMobileNavigation = computed(
  () => isNavOpen.value && isMobileNavigationViewport.value,
);
const topbarRef = ref<HTMLElement | null>(null);
const accountMenuRef = ref<HTMLDetailsElement | null>(null);
const currentUserQuery = useCurrentUser();
const mobileBoardsQuery = useBoards(shouldShowMobileNavigation);
const mobileTagsQuery = useTags(30, shouldShowMobileNavigation);
const siteSettingsQuery = usePublicSiteSettings();
const logout = useLogout();
const { locale } = useLocale();
let profileRoutePrefetched = false;
let adminRoutePrefetched = false;
let moderationRoutePrefetched = false;
const DEFAULT_BRAND_LOGO_URL = "/logo-lines-mark.png";
const LEGACY_BRAND_LOGO_URLS = new Set(["/logo-lines.png", "/favicon.svg"]);
const PUBLIC_ROUTE_PREFETCH_DELAY_MS = 2_400;
const ACCOUNT_ROUTE_PREFETCH_DELAY_MS = 1_800;
const IDLE_PREFETCH_TIMEOUT_MS = 4_000;
const currentUser = computed(() => currentUserQuery.data.value);
// Normalizes deferred taxonomy results into stable arrays consumed by the reusable rail.
// Parameters: none. Return values are current board/tag lists; side effect: none.
const mobileNavigationBoards = computed(() => mobileBoardsQuery.data.value ?? []);
const mobileNavigationTags = computed(() => mobileTagsQuery.data.value ?? []);
// Auth route already renders the login/register form, so the guest CTA is hidden there to avoid duplicate entry points.
const isAuthRoute = computed(() => route.name === "auth");
// Marks protected administration pages so they render in the dedicated operations-console shell.
// No parameters; return value follows the current route and has no side effects.
const isAdminConsoleRoute = computed(() => route.path === "/admin" || route.path.startsWith("/admin/"));
const isMobileFullscreenRoute = computed(() => route.name === "admin-moderation");
// isProfileScreenRoute 用途：标记用户资料/个人中心路由，供移动端切换为设计稿式页面外壳；无参数，返回布尔值且无副作用。
const isProfileScreenRoute = computed(() =>
  route.name === "user-profile" ||
  route.name === "account-home" ||
  route.name === "account-profile" ||
  route.name === "account-settings",
);
const isRouteNavigating = ref(false);
const siteTitle = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "site_title", "平行线"),
);
const siteTagline = computed(() =>
  publicSettingString(siteSettingsQuery.data.value, "site_tagline", "让答案可追溯"),
);
const routeSeoMeta = computed(() =>
  resolveRouteSeoMeta(route.meta.seo, {
    routePath: route.path,
    siteTitle: siteTitle.value,
    siteTagline: siteTagline.value,
  }),
);
const brandLogoUrl = computed(() => {
  const configuredLogo = publicSettingString(
    siteSettingsQuery.data.value,
    "brand_logo_url",
    DEFAULT_BRAND_LOGO_URL,
  );
  return LEGACY_BRAND_LOGO_URLS.has(configuredLogo) ? DEFAULT_BRAND_LOGO_URL : configuredLogo;
});
const brandHomeLabel = computed(() => t("brand.home_aria", "返回首页"));
const adminLinkTarget = computed<RouteLocationRaw>(() =>
  isAdmin(currentUser.value) ? { name: "admin-dashboard" } : { name: "admin-moderation" },
);
// publishLinkTarget 用途：顶部发布入口在版块页携带当前版块 slug；无参数，返回 Vue Router 目标对象且无副作用。
const publishLinkTarget = computed<RouteLocationRaw>(() => {
  const boardSlug = route.name === "board-detail" ? readRouteParam(route.params.slug) : "";
  return boardSlug ? { name: "new-topic", query: { board: boardSlug } } : { name: "new-topic" };
});
const adminLinkLabel = computed(() =>
  isAdmin(currentUser.value) ? t("nav.admin", "后台") : t("nav.moderation", "审核"),
);
const ADMIN_ROUTE_NAMES = new Set([
  "admin-dashboard",
  "admin-analytics",
  "admin-users",
]);
const isAdminLinkActive = computed(() => {
  if (!isAdmin(currentUser.value)) {
    return route.name === "admin-moderation";
  }
  return typeof route.name === "string" && ADMIN_ROUTE_NAMES.has(route.name);
});
const showSeparateModerationLink = computed(() => isAdmin(currentUser.value));
const canSubmitGlobalSearch = computed(() => Boolean(globalSearch.value.trim()));
const isCurrentUserProfileActive = computed(() => {
  if (!currentUser.value) {
    return false;
  }

  return (
    route.name === "account-home" ||
    route.name === "account-profile" ||
    route.name === "account-settings" ||
    route.name === "account-preferences" ||
    (route.name === "user-profile" && String(route.params.id ?? "") === currentUser.value.id)
  );
});
let routeFeedbackTimer: number | undefined;
const removeRouteStartGuard = router.beforeEach((to, from) => {
  if (to.fullPath === from.fullPath) {
    return true;
  }

  window.clearTimeout(routeFeedbackTimer);
  isRouteNavigating.value = false;
  routeFeedbackTimer = window.setTimeout(() => {
    isRouteNavigating.value = true;
  }, 80);
  return true;
});
const removeRouteEndGuard = router.afterEach(() => finishRouteNavigation());
const removeRouteErrorHandler = router.onError(() => finishRouteNavigation());

watchEffect(() => {
  applySiteBranding(siteSettingsQuery.data.value?.settings);
});
useSeoMeta(routeSeoMeta);

watch(
  currentUser,
  (user) => {
    if (user?.interface_theme) {
      setInterfaceTheme(user.interface_theme);
    }
  },
  { immediate: true },
);

watch(
  () => route.fullPath,
  () => {
    closeNavigation();
    closeAccountMenu();
  },
);

watch(
  [currentUser, isDesktopViewport],
  ([user, isDesktop]) => {
    if (user && isDesktop) {
      scheduleAccountRoutePrefetch(user);
    }
  },
  { immediate: true },
);

schedulePublicRoutePrefetch();

onUnmounted(() => {
  removeRouteStartGuard();
  removeRouteEndGuard();
  removeRouteErrorHandler();
  window.clearTimeout(routeFeedbackTimer);
});

useOutsidePointerDown(topbarRef, closeNavigation, () => isNavOpen.value);
useOutsidePointerDown(accountMenuRef, closeAccountMenu, () => Boolean(accountMenuRef.value?.open));

async function handleLogout() {
  closeAccountMenu();
  await logout();
}

// Keeps the brand click deterministic: it closes transient menus and scrolls home to the top when already there.
// Key parameters: none. Side effects: closes topbar popovers and may scroll the window.
function handleBrandClick() {
  closeNavigation();
  closeAccountMenu();
  if (route.name === "home") {
    window.scrollTo({ top: 0, left: 0, behavior: "smooth" });
  }
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

// Ends the visible route feedback once Vue Router has resolved the navigation or failed it.
// Key parameters: none. Side effects: clears the delayed progress timer and hides the progress bar.
function finishRouteNavigation() {
  window.clearTimeout(routeFeedbackTimer);
  isRouteNavigating.value = false;
}

// Warms the common public route chunks after first paint so topbar and mobile menu clicks feel immediate.
// Key parameters: none. Side effect: schedules lazy component imports during idle time.
function schedulePublicRoutePrefetch() {
  scheduleIdleTask(() => {
    void import("@/pages/home/HomePage.vue");
    void import("@/pages/board/BoardDirectoryPage.vue");
    void import("@/pages/play/PlayHubPage.vue");
    void import("@/pages/tools/ToolsPage.vue");
    void import("@/pages/user/UserDirectoryPage.vue");
    void import("@/pages/events/EventsPage.vue");
    void import("@/pages/search/SearchPage.vue");
    void import("@/pages/auth/AuthPage.vue");
  }, PUBLIC_ROUTE_PREFETCH_DELAY_MS);
}

// Prefetches account-only routes after the desktop shell is stable; mobile loads them on demand.
// Key parameter: `user` decides which privileged route can be prefetched. Side effect: starts idle-time imports.
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
  }, ACCOUNT_ROUTE_PREFETCH_DELAY_MS);
}

// Schedules non-critical work after the initial route has had time to fetch and paint.
// Key parameters: `callback` runs once and `delayMs` keeps route prefetches off the critical path. Side effect: registers timers/idle callbacks.
function scheduleIdleTask(callback: () => void, delayMs: number) {
  window.setTimeout(() => {
    void runWhenBrowserIdle(IDLE_PREFETCH_TIMEOUT_MS).then(callback);
  }, delayMs);
}

function t(key: string, fallback: string) {
  return siteText(siteSettingsQuery.data.value, key, fallback, locale.value);
}

</script>



<template>
  <AdminConsoleShell v-if="isAdminConsoleRoute">
    <Transition name="route-progress">
      <div v-if="isRouteNavigating" class="route-progress" aria-hidden="true">
        <span />
      </div>
    </Transition>
    <slot />
  </AdminConsoleShell>

  <div
    v-else
    class="app-shell"
    :class="{
      'is-route-navigating': isRouteNavigating,
      'app-shell--mobile-fullscreen': isMobileFullscreenRoute,
      'app-shell--auth-immersive': isAuthRoute,
      'app-shell--profile-screen': isProfileScreenRoute,
    }"
  >
    <header v-if="!isAuthRoute" ref="topbarRef" class="topbar" @keydown.esc="closeNavigation">
      <RouterLink class="brand" to="/" :aria-label="brandHomeLabel" :title="brandHomeLabel" @click="handleBrandClick">
        <span class="brand-mark">
          <img class="brand-logo" :src="brandLogoUrl" alt="" aria-hidden="true" />
        </span>
        <span>
          <strong>{{ siteTitle }}</strong>
          <small>{{ siteTagline }}</small>
        </span>
      </RouterLink>

      <form
        v-if="isDesktopViewport"
        class="search-box"
        role="search"
        :aria-label="t('search.aria', '搜索平行线')"
        @submit.prevent="submitGlobalSearch"
      >
        <SearchOutlined class="search-box__icon" aria-hidden="true" />
        <input
          v-model="globalSearch"
          type="search"
          :placeholder="t('search.placeholder', '搜索主题、标签、作者')"
        />
        <button
          class="global-search-submit"
          type="submit"
          :disabled="!canSubmitGlobalSearch"
          :aria-label="t('search.submit_aria', '按回车搜索')"
          :title="t('search.submit_aria', '按回车搜索')"
        >
          <EnterOutlined />
        </button>
      </form>

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
          v-if="isDesktopViewport"
          class="auth-link"
          :class="{ 'is-active': route.name === 'tools' || route.name === 'daily-report' }"
          :to="{ name: 'tools' }"
        >
          <ToolOutlined aria-hidden="true" />
          工具
        </RouterLink>

        <PluginSlot v-if="isDesktopViewport" class="desktop-plugin-slot" slot-name="app.nav" />

        <NotificationBell v-if="currentUser" class="topbar-notification" />

        <template v-if="!currentUser">
          <RouterLink v-if="!isAuthRoute" class="auth-link auth-link--guest" :to="{ name: 'auth' }">
            {{ t("auth.login_register", "登录/注册") }}
          </RouterLink>
        </template>
        <template v-else>
          <details ref="accountMenuRef" class="account-menu" @keydown.esc="closeAccountMenu">
            <summary
              class="account-menu__summary"
              :class="{ 'is-active': isCurrentUserProfileActive }"
              :aria-label="t('nav.account_menu', '打开账号菜单')"
            >
              <UserOutlined class="account-menu__icon" aria-hidden="true" />
              <span>
                <strong>{{ t("nav.profile", "个人中心") }}</strong>
                <small>@{{ currentUser.username }}</small>
              </span>
              <DownOutlined class="account-menu__chevron" />
            </summary>
            <div class="account-menu__panel">
              <RouterLink
                class="account-menu__item account-menu__item--profile"
                :to="{ name: 'account-home' }"
                :class="{ 'is-active': route.name === 'account-home' || route.name === 'account-profile' }"
                @click="closeAccountMenu"
              >
                <span>{{ t("nav.profile", "个人中心") }}</span>
                <small>{{ currentUser.points_balance }} 可用积分</small>
              </RouterLink>
              <RouterLink
                v-if="canAccessModeration(currentUser)"
                class="account-menu__item"
                :to="adminLinkTarget"
                :class="{ 'is-active': isAdminLinkActive }"
                @click="closeAccountMenu"
              >
                {{ adminLinkLabel }}
              </RouterLink>
              <RouterLink
                v-if="showSeparateModerationLink"
                class="account-menu__item"
                :to="{ name: 'admin-moderation' }"
                :class="{ 'is-active': route.name === 'admin-moderation' }"
                @click="closeAccountMenu"
              >
                {{ t("nav.moderation", "审核") }}
              </RouterLink>
              <RouterLink
                class="account-menu__item"
                :to="{ name: 'tools' }"
                :class="{ 'is-active': route.name === 'tools' || route.name === 'daily-report' }"
                @click="closeAccountMenu"
              >
                社区工具
              </RouterLink>
              <RouterLink
                class="account-menu__item"
                :to="{ name: 'account-settings' }"
                :class="{ 'is-active': route.name === 'account-settings' }"
                @click="closeAccountMenu"
              >
                {{ t("nav.account_settings", "账号设置") }}
              </RouterLink>
              <RouterLink
                class="account-menu__item"
                :to="{ name: 'account-preferences' }"
                :class="{ 'is-active': route.name === 'account-preferences' }"
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
              <button class="account-menu__item account-menu__item--danger" type="button" @click="handleLogout">
                {{ t("auth.logout", "退出") }}
              </button>
            </div>
          </details>
        </template>
        <RouterLink class="publish-link" :to="publishLinkTarget" :aria-label="t('topic.publish_aria', '发布主题')">
          <UiButton tone="primary">
            <template #icon>
              <PlusOutlined />
            </template>
            <span class="publish-label">{{ t("topic.publish", "发布主题") }}</span>
          </UiButton>
        </RouterLink>
      </div>

      <div v-if="shouldShowMobileNavigation" id="mobile-navigation" class="mobile-nav-panel">
        <form
          class="mobile-search-box"
          role="search"
          :aria-label="t('search.mobile_aria', '移动端搜索平行线')"
          @submit.prevent="submitGlobalSearch"
        >
          <SearchOutlined class="search-box__icon" aria-hidden="true" />
          <input
            v-model="globalSearch"
            type="search"
            :placeholder="t('search.placeholder', '搜索主题、标签、作者')"
          />
          <button
            class="global-search-submit"
            type="submit"
            :disabled="!canSubmitGlobalSearch"
            :aria-label="t('search.submit_aria', '按回车搜索')"
            :title="t('search.submit_aria', '按回车搜索')"
          >
            <EnterOutlined />
          </button>
        </form>

        <ForumLeftRail
          variant="mobile"
          :boards="mobileNavigationBoards"
          :tags="mobileNavigationTags"
          :boards-loading="mobileBoardsQuery.isLoading.value"
          :boards-error="mobileBoardsQuery.isError.value"
          :tags-loading="mobileTagsQuery.isLoading.value"
          :tags-error="mobileTagsQuery.isError.value"
          @navigate="closeNavigation"
        />
      </div>
    </header>

    <Transition name="route-progress">
      <div v-if="isRouteNavigating" class="route-progress" aria-hidden="true">
        <span />
      </div>
    </Transition>

    <main class="shell-main">
      <slot />
    </main>
  </div>
</template>

<style scoped lang="scss" src="./AppShell.scss"></style>

