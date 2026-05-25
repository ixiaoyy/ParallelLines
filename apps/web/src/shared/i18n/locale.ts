import { ref } from "vue";

export type AppLocale = "zh-CN" | "en-US";

export const supportedLocales: { value: AppLocale; label: string }[] = [
  { value: "zh-CN", label: "中文" },
  { value: "en-US", label: "English" },
];

const STORAGE_KEY = "parallellines.locale";
const supportedLocaleValues = new Set<AppLocale>(supportedLocales.map((item) => item.value));

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

export function setLocale(nextLocale: string) {
  if (!isSupportedLocale(nextLocale)) {
    return;
  }

  currentLocale.value = nextLocale;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, nextLocale);
  }
  if (typeof document !== "undefined") {
    document.documentElement.lang = nextLocale;
  }
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

  return EN_SITE_TEXT[key] ?? fallback;
}

function readInitialLocale(): AppLocale {
  if (typeof window === "undefined") {
    return "zh-CN";
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored && isSupportedLocale(stored)) {
    return stored;
  }

  const browserLocale = window.navigator.language;
  return browserLocale.toLowerCase().startsWith("en") ? "en-US" : "zh-CN";
}

function isSupportedLocale(value: string): value is AppLocale {
  return supportedLocaleValues.has(value as AppLocale);
}

const EN_SITE_TEXT: Record<string, string> = {
  "auth.login_register": "Log in / Sign up",
  "auth.logout": "Log out",
  "brand.home_aria": "Parallel Lines home",
  "nav.admin": "Admin",
  "nav.billing": "Membership",
  "nav.boards": "Boards",
  "nav.chat": "Chat",
  "nav.collapse": "Close",
  "nav.collapse_aria": "Collapse navigation",
  "nav.email": "Email",
  "nav.events": "Events",
  "nav.expand_aria": "Expand navigation",
  "nav.home": "Home",
  "nav.menu": "Menu",
  "nav.messages": "Messages",
  "nav.moderation": "Moderation",
  "nav.reviewables": "Appeals",
  "nav.security": "Security",
  "nav.users": "Members",
  "search.aria": "Search Parallel Lines",
  "search.mobile_aria": "Search Parallel Lines on mobile",
  "search.placeholder": "Search topics, tags, authors",
  "topic.publish": "New topic",
  "topic.publish_aria": "Publish topic",
};
