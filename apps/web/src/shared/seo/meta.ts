import { toValue, watchEffect } from "vue";
import type { MaybeRefOrGetter } from "vue";

export interface SeoMetaInput {
  title: string;
  description: string;
  canonicalPath: string;
  ogType?: "website" | "article" | string;
  robots?: string;
  siteName?: string;
  locale?: string;
}

export interface RouteSeoMeta {
  title: string;
  description: string;
  canonicalPath?: string;
  ogType?: "website" | "article" | string;
  robots?: string;
}

export function useSeoMeta(source: MaybeRefOrGetter<SeoMetaInput | null | undefined>) {
  watchEffect(() => {
    const meta = toValue(source);
    if (!meta || typeof document === "undefined") {
      return;
    }

    const canonicalUrl = absoluteUrl(meta.canonicalPath);
    const description = truncateSeoDescription(meta.description);
    document.title = meta.title;
    setMeta("name", "description", description);
    setMeta("name", "robots", meta.robots ?? "index,follow");
    setMeta("property", "og:type", meta.ogType ?? "website");
    setMeta("property", "og:title", meta.title);
    setMeta("property", "og:description", description);
    setMeta("property", "og:url", canonicalUrl);
    if (meta.siteName) {
      setMeta("property", "og:site_name", meta.siteName);
    }
    setMeta("property", "og:locale", meta.locale ?? "zh_CN");
    setMeta("name", "twitter:card", "summary");
    setMeta("name", "twitter:title", meta.title);
    setMeta("name", "twitter:description", description);
    setCanonical(canonicalUrl);
  });
}

/**
 * Resolves route meta into concrete SEO tags for the current navigation target.
 *
 * @param routeSeo - Static SEO config attached to a Vue Router route.
 * @param context - Current route path and site-level title/tagline settings.
 * @returns Complete SEO meta ready for `useSeoMeta`; side effect: none.
 */
export function resolveRouteSeoMeta(
  routeSeo: RouteSeoMeta | undefined,
  context: { routePath: string; siteTitle: string; siteName?: string; siteTagline: string },
): SeoMetaInput {
  const canonicalPath = routeSeo?.canonicalPath ?? cleanRoutePath(context.routePath);
  return {
    title: formatSeoTemplate(routeSeo?.title ?? "{siteTitle}", context),
    description: formatSeoTemplate(routeSeo?.description ?? "{siteTagline}", context),
    canonicalPath,
    ogType: routeSeo?.ogType,
    robots: routeSeo?.robots,
    siteName: context.siteName ?? context.siteTitle,
    locale: "zh_CN",
  };
}

function absoluteUrl(path: string) {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }

  const origin = typeof window === "undefined" ? "" : window.location.origin;
  return `${origin}${path.startsWith("/") ? path : `/${path}`}`;
}

function setMeta(attribute: "name" | "property", key: string, content: string) {
  const selector = `meta[${attribute}="${cssEscape(key)}"]`;
  let element = document.head.querySelector<HTMLMetaElement>(selector);
  if (!element) {
    element = document.createElement("meta");
    element.setAttribute(attribute, key);
    element.dataset.managedBy = "parallellines-seo";
    document.head.append(element);
  }
  element.setAttribute("content", content);
}

function setCanonical(href: string) {
  let element = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!element) {
    element = document.createElement("link");
    element.rel = "canonical";
    element.dataset.managedBy = "parallellines-seo";
    document.head.append(element);
  }
  element.href = href;
}

function cssEscape(value: string) {
  return value.replace(/"/g, '\\"');
}

/**
 * Applies site-level placeholders used by route SEO definitions.
 *
 * @param template - Route SEO text containing optional `{siteTitle}`, `{siteName}`, or `{siteTagline}` placeholders.
 * @param context - Public site title/tagline plus the optional unique SEO site name.
 * @returns SEO text with placeholders replaced. Side effect: none.
 */
function formatSeoTemplate(
  template: string,
  context: { siteTitle: string; siteName?: string; siteTagline: string },
): string {
  const siteName = context.siteName ?? context.siteTitle;
  return template
    .replaceAll("{siteTitle}", context.siteTitle)
    .replaceAll("{siteName}", siteName)
    .replaceAll("{siteTagline}", context.siteTagline);
}

/**
 * Normalizes a route path before using it as a canonical fallback.
 *
 * @param routePath - Current Vue Router path without query or hash.
 * @returns A non-empty absolute path beginning with `/`. Side effect: none.
 */
function cleanRoutePath(routePath: string): string {
  return routePath.startsWith("/") && routePath ? routePath : "/";
}

/**
 * Normalizes and bounds metadata copy to the same 180-character server contract.
 *
 * @param value - Dynamic route or entity description.
 * @returns Compact description text with an ellipsis when truncated. Side effect: none.
 */
function truncateSeoDescription(value: string): string {
  const compact = value.replace(/\s+/g, " ").trim();
  return compact.length <= 180 ? compact : `${compact.slice(0, 179).trimEnd()}…`;
}
