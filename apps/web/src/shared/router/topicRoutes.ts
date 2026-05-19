import type { RouteLocationNamedRaw } from "vue-router";

export interface TopicRouteTarget {
  id: string;
  slug?: string | null;
  hash?: string | number | null;
}

export function topicDetailRoute(target: TopicRouteTarget): RouteLocationNamedRaw {
  return {
    name: "topic-detail",
    params: {
      id: target.id,
      slug: normalizeTopicSlug(target.slug),
    },
    hash: normalizeRouteHash(target.hash),
  };
}

export function topicDetailPath(target: TopicRouteTarget) {
  const id = encodeRouteSegment(target.id);
  const slug = encodeRouteSegment(normalizeTopicSlug(target.slug));
  return `/topics/${id}/${slug}${normalizeRouteHash(target.hash)}`;
}

export function normalizeTopicSlug(slug: string | null | undefined) {
  const value = slug?.trim();
  return value || "topic";
}

function normalizeRouteHash(hash: TopicRouteTarget["hash"]) {
  if (hash === null || hash === undefined || hash === "") {
    return "";
  }

  const value = String(hash);
  return value.startsWith("#") ? value : `#${value}`;
}

function encodeRouteSegment(value: string) {
  return encodeURIComponent(value).replace(/%2F/gi, "-");
}
