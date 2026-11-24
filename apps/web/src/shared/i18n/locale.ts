import { ref } from "vue";

import { EN_UI_TEXT } from "./en";

export type AppLocale = "zh-CN" | "en-US";

export const supportedLocales: { value: AppLocale; label: string }[] = [
  { value: "zh-CN", label: "简体中文" },
  { value: "en-US", label: "English" },
];

const STORAGE_KEY = "parallellines.locale";
const supportedLocaleValues = new Set<AppLocale>(supportedLocales.map((item) => item.value));

export const localePersistenceAvailable = ref(true);
export const currentLocale = ref<AppLocale>(readInitialLocale());
if (typeof document !== "undefined") {
  document.documentElement.lang = currentLocale.value;
}

export function useLocale() {
  return {
    locale: currentLocale,
    supportedLocales,
    setLocale,
  };
}

/** 切换本页界面并保存浏览器偏好；存储受限时保留本页选择并由切换器明确提示。 */
export function setLocale(nextLocale: string) {
  if (!isSupportedLocale(nextLocale)) {
    return;
  }

  currentLocale.value = nextLocale;
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(STORAGE_KEY, nextLocale);
      localePersistenceAvailable.value = true;
    } catch {
      localePersistenceAvailable.value = false;
    }
  }
  if (typeof document !== "undefined") {
    document.documentElement.lang = nextLocale;
  }
}

/** 翻译本站界面文案并替换命名参数；未收录的内容保留原文，不用于帖子、游戏名或用户输入。 */
export function uiText(source: string, params: Record<string, string | number> = {}): string {
  const text = currentLocale.value === "en-US" && Object.prototype.hasOwnProperty.call(EN_UI_TEXT, source)
    ? EN_UI_TEXT[source] : source;
  return text.replace(/\{(\w+)\}/g, (placeholder, name: string) =>
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : placeholder,
  );
}

export function localizedText(
  localizations: Record<string, string> | null | undefined,
  fallback: string,
  locale: AppLocale = currentLocale.value,
): string {
  if (!localizations) {
    return fallback;
  }

  const exact = localizations[locale];
  if (typeof exact === "string" && exact.trim()) {
    return exact;
  }

  const language = locale.split("-", 1)[0];
  const languageOnly = localizations[language];
  return typeof languageOnly === "string" && languageOnly.trim() ? languageOnly : fallback;
}

export function builtinSiteText(key: string, fallback: string, locale: AppLocale): string {
  if (locale === "zh-CN") {
    return fallback;
  }

  if (Object.prototype.hasOwnProperty.call(EN_SITE_TEXT, key)) return EN_SITE_TEXT[key];
  if (Object.prototype.hasOwnProperty.call(EN_UI_TEXT, key)) return EN_UI_TEXT[key];
  return Object.prototype.hasOwnProperty.call(EN_UI_TEXT, fallback) ? EN_UI_TEXT[fallback] : fallback;
}

function readInitialLocale(): AppLocale {
  if (typeof window === "undefined") {
    return "zh-CN";
  }

  // 手动选择优先；浏览器禁用存储时仍允许首次按浏览器语言进入和本页切换。
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && isSupportedLocale(stored)) return stored;
  } catch {
    localePersistenceAvailable.value = false;
  }

  const browserLocale = window.navigator?.language ?? "";
  return browserLocale.toLowerCase().startsWith("en") ? "en-US" : "zh-CN";
}

function isSupportedLocale(value: string): value is AppLocale {
  return supportedLocaleValues.has(value as AppLocale);
}

const EN_SITE_TEXT: Record<string, string> = {
  "auth.login_register": "Log in / Sign up",
  "auth.login": "Log in",
  "auth.logout": "Log out",
  "brand.home_aria": "ParallelLines home",
  "admin.nav.dashboard": "Dashboard",
  "admin.nav.dashboard_short": "Dashboard",
  "admin.nav.analytics": "Cross-site analytics",
  "admin.nav.analytics_short": "Analytics",
  "admin.nav.users": "Users",
  "admin.nav.users_short": "Users",
  "admin.nav.moderation": "Moderation",
  "admin.nav.moderation_short": "Review",
  "admin.nav.system": "System health",
  "admin.nav.system_short": "System",
  "account.role.admin": "Administrator",
  "account.role.moderator": "Moderator",
  "account.role.user": "User",
  "account.status.active": "Active",
  "account.status.deleted": "Deleted",
  "account.status.pending_verification": "Unverified",
  "account.status.silenced": "Silenced",
  "account.status.suspended": "Suspended",
  "nav.account_settings": "Account settings",
  "nav.account_menu": "Open account menu",
  "nav.admin": "Admin",
  "nav.boards": "Boards",
  "nav.collapse": "Close",
  "nav.collapse_aria": "Collapse navigation",
  "nav.email": "Email",
  "nav.events": "Events",
  "nav.expand_aria": "Expand navigation",
  "nav.home": "Home",
  "nav.menu": "Menu",
  "nav.messages": "Messages",
  "nav.moderation": "Moderation",
  "nav.profile": "Profile",
  "nav.users": "Members",
  "search.aria": "Search Parallel Lines",
  "search.mobile_aria": "Search Parallel Lines on mobile",
  "search.placeholder": "Search topics, tags, authors",
  "search.submit_aria": "Press Enter to search",
  "topic.publish": "New topic",
  "topic.publish_aria": "Publish topic",
};
