import { toValue, watchEffect } from "vue";
import type { MaybeRefOrGetter } from "vue";

export interface SeoMetaInput {
  title: string;
  description: string;
  canonicalPath: string;
  ogType?: "website" | "article" | string;
}

export function useSeoMeta(source: MaybeRefOrGetter<SeoMetaInput | null | undefined>) {
  watchEffect(() => {
    const meta = toValue(source);
    if (!meta || typeof document === "undefined") {
      return;
    }

    const canonicalUrl = absoluteUrl(meta.canonicalPath);
    document.title = meta.title;
    setMeta("name", "description", meta.description);
    setMeta("name", "robots", "index,follow");
    setMeta("property", "og:type", meta.ogType ?? "website");
    setMeta("property", "og:title", meta.title);
    setMeta("property", "og:description", meta.description);
    setMeta("property", "og:url", canonicalUrl);
    setMeta("name", "twitter:card", "summary");
    setMeta("name", "twitter:title", meta.title);
    setMeta("name", "twitter:description", meta.description);
    setCanonical(canonicalUrl);
  });
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
