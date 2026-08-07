import { onUnmounted, toValue, watchEffect } from "vue";
import type { MaybeRefOrGetter } from "vue";

export const SEO_SITE_STRUCTURED_DATA_ID = "seo-site-structured-data";
export const SEO_PAGE_STRUCTURED_DATA_ID = "seo-page-structured-data";
export const SEO_BRAND_NAME = "ParallelLines";

const SEO_DEFAULT_PUBLIC_TITLE = "平行线";

export type JsonLdValue = string | number | boolean | null | JsonLdObject | JsonLdValue[];

export interface JsonLdObject {
  [key: string]: JsonLdValue;
}

export interface SiteStructuredDataInput {
  siteUrl: string;
  title: string;
  description: string;
  logoUrl: string;
}

export interface ForumPostStructuredDataInput {
  authorName: string;
  publishedAt: string;
  modifiedAt?: string;
  postNumber: number;
  text: string;
}

export interface ForumTopicStructuredDataInput {
  topicUrl: string;
  title: string;
  boardName: string;
  boardUrl: string;
  publishedAt: string;
  modifiedAt?: string;
  authorName: string;
  text: string;
  replyCount: number;
  viewCount: number;
  likeCount: number;
  replies: ForumPostStructuredDataInput[];
}

export interface ProfileStructuredDataInput {
  profileUrl: string;
  username: string;
  displayName: string;
  bio: string | null;
  avatarUrl: string | null;
  createdAt: string;
  topicCount: number;
  postCount: number;
}

/**
 * Owns one stable JSON-LD DOM slot for a reactive structured-data source.
 *
 * @param slotId - Controlled site/page script ID shared with server rendering.
 * @param source - `undefined` preserves server HTML while data loads, `null` removes the slot, and an object replaces it.
 * @returns Nothing. Side effects: updates the document head reactively and removes the slot when its owner unmounts.
 */
export function useStructuredData(
  slotId: string,
  source: MaybeRefOrGetter<JsonLdObject | null | undefined>,
): void {
  watchEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    const value = toValue(source);
    if (value === undefined) {
      return;
    }
    if (value === null) {
      removeStructuredData(slotId);
      return;
    }
    upsertStructuredData(slotId, value);
  });

  onUnmounted(() => {
    if (typeof document !== "undefined") {
      removeStructuredData(slotId);
    }
  });
}

/**
 * Builds persistent WebSite and Organization schema from public brand settings.
 *
 * @param input - Canonical origin, public site copy, and the configured existing logo URL.
 * @returns A JSON-LD graph with stable site/entity IDs. Side effect: none.
 */
export function buildSiteStructuredData(input: SiteStructuredDataInput): JsonLdObject {
  const siteUrl = absoluteSeoUrl(input.siteUrl, "/");
  const websiteId = `${siteUrl}#website`;
  const organizationId = `${siteUrl}#organization`;
  const siteName = buildSeoSiteName(input.title);
  const alternateNames = buildSeoSiteAlternateNames(input.title, siteUrl);
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite",
        "@id": websiteId,
        url: siteUrl,
        name: siteName,
        alternateName: alternateNames,
        description: input.description,
        inLanguage: "zh-CN",
        publisher: { "@id": organizationId },
      },
      {
        "@type": "Organization",
        "@id": organizationId,
        url: siteUrl,
        name: siteName,
        alternateName: alternateNames,
        logo: {
          "@type": "ImageObject",
          url: absoluteSeoUrl(input.siteUrl, input.logoUrl),
        },
      },
    ],
  };
}

/**
 * Builds the unique bilingual SEO name from the configurable public title.
 *
 * @param publicTitle - Administrator-visible site title.
 * @returns The trimmed title with the stable Latin brand appended exactly once. Side effect: none.
 */
export function buildSeoSiteName(publicTitle: string): string {
  const title = publicTitle.trim() || SEO_DEFAULT_PUBLIC_TITLE;
  return title.toLowerCase().includes(SEO_BRAND_NAME.toLowerCase())
    ? title
    : `${title} ${SEO_BRAND_NAME}`;
}

/**
 * Builds legitimate alternate names for the site-name structured-data contract.
 *
 * @param publicTitle - Administrator-visible site title.
 * @param siteUrl - Absolute canonical site URL used to derive the lowercase hostname backup.
 * @returns Deduplicated human-readable and hostname aliases in preference order. Side effect: none.
 */
export function buildSeoSiteAlternateNames(publicTitle: string, siteUrl: string): string[] {
  const primaryName = buildSeoSiteName(publicTitle).toLowerCase();
  const hostname = new URL(siteUrl).hostname.toLowerCase();
  const candidates = [publicTitle.trim(), SEO_DEFAULT_PUBLIC_TITLE, SEO_BRAND_NAME, hostname];
  const seen = new Set([primaryName]);
  return candidates.filter((candidate) => {
    const normalized = candidate.trim();
    const key = normalized.toLowerCase();
    if (!normalized || seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

/**
 * Builds DiscussionForumPosting schema from a confirmed public topic and its visible posts.
 *
 * @param input - Canonical topic/board URLs, public counters, first-post text, and a bounded reply list.
 * @returns JSON-LD matching the content currently rendered by the topic page. Side effect: none.
 */
export function buildForumTopicStructuredData(
  input: ForumTopicStructuredDataInput,
): JsonLdObject {
  const comments: JsonLdObject[] = input.replies.map((reply) => {
    const comment: JsonLdObject = {
      "@type": "Comment",
      url: `${input.topicUrl}#post-${reply.postNumber}`,
      text: reply.text,
      datePublished: reply.publishedAt,
      author: { "@type": "Person", name: reply.authorName },
    };
    if (reply.modifiedAt) {
      comment.dateModified = reply.modifiedAt;
    }
    return comment;
  });
  const schema: JsonLdObject = {
    "@context": "https://schema.org",
    "@type": "DiscussionForumPosting",
    url: input.topicUrl,
    mainEntityOfPage: input.topicUrl,
    headline: input.title,
    text: input.text,
    articleBody: input.text,
    datePublished: input.publishedAt,
    author: { "@type": "Person", name: input.authorName },
    commentCount: input.replyCount,
    interactionStatistic: [
      interactionCounter("https://schema.org/ViewAction", input.viewCount),
      interactionCounter("https://schema.org/LikeAction", input.likeCount),
      interactionCounter("https://schema.org/CommentAction", input.replyCount),
    ],
    isPartOf: {
      "@type": "CollectionPage",
      name: input.boardName,
      url: input.boardUrl,
    },
    inLanguage: "zh-CN",
  };
  if (input.modifiedAt) {
    schema.dateModified = input.modifiedAt;
  }
  if (comments.length > 0) {
    schema.comment = comments;
  }
  return schema;
}

/**
 * Builds ProfilePage and Person schema for one profile confirmed as public.
 *
 * @param input - Canonical profile URL plus public identity fields and contribution counts.
 * @returns Public profile JSON-LD without members-only/private fields. Side effect: none.
 */
export function buildProfileStructuredData(input: ProfileStructuredDataInput): JsonLdObject {
  const person: JsonLdObject = {
    "@type": "Person",
    "@id": `${input.profileUrl}#person`,
    name: input.displayName,
    alternateName: input.username,
    url: input.profileUrl,
  };
  if (input.bio) {
    person.description = input.bio;
  }
  if (input.avatarUrl) {
    person.image = input.avatarUrl;
  }
  return {
    "@context": "https://schema.org",
    "@type": "ProfilePage",
    url: input.profileUrl,
    dateCreated: input.createdAt,
    mainEntity: person,
    interactionStatistic: [
      {
        ...interactionCounter("https://schema.org/CreateAction", input.topicCount),
        name: "公开主题",
      },
      {
        ...interactionCounter("https://schema.org/WriteAction", input.postCount),
        name: "公开帖子",
      },
    ],
    inLanguage: "zh-CN",
  };
}

/**
 * Converts a Markdown fragment to compact visible plain text for JSON-LD.
 *
 * @param value - Public post Markdown.
 * @returns Text with image targets, link targets, fences, and lightweight markers removed. Side effect: none.
 */
export function markdownToPlainText(value: string): string {
  return value
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/```[^\n]*\n?([\s\S]*?)```/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/[*_>#\[\]()`~]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Resolves ``path`` against an absolute canonical ``origin``.
 *
 * @param origin - Browser/site HTTP(S) origin.
 * @param path - Root-relative or absolute URL from trusted application data.
 * @returns An absolute URL string. Side effect: none.
 */
export function absoluteSeoUrl(origin: string, path: string): string {
  return new URL(path, `${origin.replace(/\/$/, "")}/`).toString();
}

/**
 * Returns the active browser origin used after canonical host redirects.
 *
 * @returns `window.location.origin` in a browser, otherwise `undefined`. Side effect: none.
 */
export function browserSeoOrigin(): string | undefined {
  return typeof window === "undefined" ? undefined : window.location.origin;
}

/**
 * Upserts a single application/ld+json script under controlled ``slotId``.
 *
 * @param slotId - Stable internal DOM ID.
 * @param value - JSON-LD object to serialize through textContent.
 * @returns Nothing. Side effect: creates/replaces one document-head script without using innerHTML.
 */
function upsertStructuredData(slotId: string, value: JsonLdObject): void {
  const existing = document.getElementById(slotId);
  let script: HTMLScriptElement;
  if (existing instanceof HTMLScriptElement && existing.type === "application/ld+json") {
    script = existing;
  } else {
    script = document.createElement("script");
    script.id = slotId;
    script.type = "application/ld+json";
    script.dataset.managedBy = "parallellines-seo";
    if (existing) {
      existing.replaceWith(script);
    } else {
      document.head.append(script);
    }
  }
  script.textContent = JSON.stringify(value);
}

/**
 * Removes the controlled structured-data ``slotId`` if it exists.
 *
 * @param slotId - Stable internal DOM ID.
 * @returns Nothing. Side effect: removes at most one element from the document.
 */
function removeStructuredData(slotId: string): void {
  document.getElementById(slotId)?.remove();
}

/**
 * Builds one Schema.org interaction counter for ``interactionType`` and ``count``.
 *
 * @returns A JSON-LD object. Side effect: none.
 */
function interactionCounter(interactionType: string, count: number): JsonLdObject {
  return {
    "@type": "InteractionCounter",
    interactionType,
    userInteractionCount: count,
  };
}
