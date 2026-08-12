import type { Router, RouteLocationNormalized } from "vue-router";

import { recordSiteVisit } from "@/features/analytics/api";

const EXCLUDED_ROUTE_NAMES = new Set([
  "access-denied",
  "account-home",
  "account-preferences",
  "account-profile",
  "account-settings",
  "admin-dashboard",
  "admin-moderation",
  "auth",
  "design-system",
  "messages",
  "my-invites",
  "my-reviewables",
  "new-topic",
]);
const EXCLUDED_PATH_PREFIXES = [
  "/account",
  "/admin",
  "/auth",
  "/design-system",
  "/forbidden",
  "/invites",
  "/messages",
  "/moderation",
  "/new-topic",
];

// Installs a Vue Router hook that records public page views for PV/UV and acquisition reports.
// Key parameter `router` is the app router. Return value is none. Side effect: registers an afterEach hook.
export function installSiteVisitTracker(router: Router): void {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return;
  }

  let lastTrackedPath = "";
  let nextReferrer = document.referrer || "";

  router.afterEach((to, _from, failure) => {
    if (failure || shouldRespectDoNotTrack() || isAutomatedBrowser()) {
      nextReferrer = window.location.href;
      return;
    }
    if (!shouldTrackRoute(to)) {
      nextReferrer = window.location.href;
      return;
    }

    window.setTimeout(() => {
      const path = currentVisitPath();
      if (!path || path === lastTrackedPath) {
        nextReferrer = window.location.href;
        return;
      }

      lastTrackedPath = path;
      const referrer = nextReferrer || null;
      nextReferrer = window.location.href;
      void recordSiteVisit({
        path,
        title: document.title || null,
        referrer,
      }).catch(() => undefined);
    }, 0);
  });
}

// Decides whether a route should contribute to public traffic analytics.
// Key parameter `route` is the completed navigation target. Return value is true for public pages.
// Side effect: none.
function shouldTrackRoute(route: RouteLocationNormalized): boolean {
  if (route.meta.requiredAccess) {
    return false;
  }

  const routeName = typeof route.name === "string" ? route.name : "";
  if (EXCLUDED_ROUTE_NAMES.has(routeName)) {
    return false;
  }

  return !EXCLUDED_PATH_PREFIXES.some(
    (prefix) => route.path === prefix || route.path.startsWith(`${prefix}/`),
  );
}

// Returns the current browser path without domain or hash.
// Key parameters: none. Return value is a site-internal path plus query string. Side effect: none.
function currentVisitPath(): string {
  return `${window.location.pathname}${window.location.search}`;
}

// Honors browser-level do-not-track flags for first-party analytics collection.
// Key parameters: none. Return value is true when tracking should be skipped. Side effect: none.
function shouldRespectDoNotTrack(): boolean {
  const navigatorWithLegacyFlag = window.navigator as Navigator & { msDoNotTrack?: string };
  return navigatorWithLegacyFlag.doNotTrack === "1" || navigatorWithLegacyFlag.msDoNotTrack === "1";
}

// Excludes browser sessions that explicitly expose WebDriver automation from human-facing analytics.
// Key parameters: none. Return value is true for standards-compliant automated browsers. Side effect: none.
function isAutomatedBrowser(): boolean {
  return window.navigator.webdriver === true;
}
