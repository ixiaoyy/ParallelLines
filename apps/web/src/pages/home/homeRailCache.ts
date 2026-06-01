import type { BoardSummary } from "@/entities/board/model";
import type { TopicCardVM } from "@/entities/topic/model";
import type { TagItemVM } from "@/features/tags/model";
import type { TopicSort } from "@/features/topics/model";
import { getAccessToken, getRefreshToken } from "@/shared/api/client";
import { readPersistentCache, writePersistentCache } from "@/shared/lib/persistentCache";

const CACHE_TTL_MS = 10 * 60 * 1000;
const TOPIC_FEED_CACHE_TTL_MS = 2 * 60 * 1000;
const PUBLIC_BOARDS_CACHE_KEY = "parallellines.homeRail.publicBoards.v1";
const TAGS_CACHE_KEY_PREFIX = "parallellines.homeRail.tags.v2";
const TOPIC_FEED_CACHE_KEY_PREFIX = "parallellines.homeFeed.topics.v1";

export function readCachedHomeRailBoards(): BoardSummary[] {
  return readPersistentCache(PUBLIC_BOARDS_CACHE_KEY, isBoardSummaryArray, CACHE_TTL_MS) ?? [];
}

export function readCachedHomeRailTags(): TagItemVM[] {
  return (
    readPersistentCache(authScopedCacheKey(TAGS_CACHE_KEY_PREFIX), isTagItemArray, CACHE_TTL_MS) ??
    []
  );
}

// Read cached home feed topics for one sort while a fresh API request is loading.
// Key parameter: `sort`; return value is a validated topic list; side effects: none.
export function readCachedHomeFeedTopics(sort: TopicSort): TopicCardVM[] {
  return (
    readPersistentCache(
      `${authScopedCacheKey(TOPIC_FEED_CACHE_KEY_PREFIX)}:${sort}`,
      isTopicCardArray,
      TOPIC_FEED_CACHE_TTL_MS,
    ) ?? []
  );
}

export function cacheHomeRailBoards(boards: BoardSummary[]): BoardSummary[] {
  const publicBoards = boards
    .filter((board) => board.visibility === "public")
    .map(toPublicRailBoard);

  if (publicBoards.length) {
    writePersistentCache(PUBLIC_BOARDS_CACHE_KEY, publicBoards);
  }

  return publicBoards;
}

export function cacheHomeRailTags(tags: TagItemVM[]): TagItemVM[] {
  const publicTags = tags.slice(0, 10);
  if (!publicTags.length) {
    return publicTags;
  }

  writePersistentCache(authScopedCacheKey(TAGS_CACHE_KEY_PREFIX), publicTags);
  return publicTags;
}

// Persist the latest home feed topics for one sort to make refreshes feel instant.
// Key parameters are `sort` and `topics`; return value is the cached slice.
export function cacheHomeFeedTopics(sort: TopicSort, topics: TopicCardVM[]): TopicCardVM[] {
  const feedTopics = topics.slice(0, 30);
  if (!feedTopics.length) {
    return feedTopics;
  }

  writePersistentCache(`${authScopedCacheKey(TOPIC_FEED_CACHE_KEY_PREFIX)}:${sort}`, feedTopics);
  return feedTopics;
}

// Scope persisted data to anonymous users or one authenticated session.
// Return value: localStorage key; side effects: none.
function authScopedCacheKey(prefix: string): string {
  const authToken = getRefreshToken() ?? getAccessToken();
  if (!authToken) {
    return `${prefix}:anonymous`;
  }

  return `${prefix}:user:${hashCacheScope(authToken)}`;
}

// Derive a short, non-secret cache-key suffix from the stored token.
// Key parameter: `value` is the token; return value is a best-effort scope id.
function hashCacheScope(value: string): string {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = Math.imul(31, hash) + value.charCodeAt(index);
    hash |= 0;
  }

  return Math.abs(hash).toString(36);
}

function toPublicRailBoard(board: BoardSummary): BoardSummary {
  return {
    ...board,
    isFollowing: false,
    notificationLevel: null,
    canCreateTopic: true,
  };
}

function isBoardSummaryArray(value: unknown): value is BoardSummary[] {
  return Array.isArray(value) && value.every(isBoardSummary);
}

function isBoardSummary(value: unknown): value is BoardSummary {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.id === "string" &&
    typeof value.slug === "string" &&
    typeof value.name === "string" &&
    typeof value.description === "string" &&
    typeof value.color === "string" &&
    typeof value.visibility === "string" &&
    Array.isArray(value.requiredTags) &&
    Array.isArray(value.allowedTags) &&
    typeof value.topicCount === "number" &&
    typeof value.postCount === "number" &&
    typeof value.followerCount === "number"
  );
}

function isTagItemArray(value: unknown): value is TagItemVM[] {
  return Array.isArray(value) && value.every(isTagItem);
}

function isTagItem(value: unknown): value is TagItemVM {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.slug === "string" &&
    typeof value.topicCount === "number"
  );
}

// Validate persisted home feed arrays before using them as UI data.
// Return value narrows unknown cache payloads to `TopicCardVM[]`; side effects: none.
function isTopicCardArray(value: unknown): value is TopicCardVM[] {
  return Array.isArray(value) && value.every(isTopicCard);
}

// Validate the minimal topic-card fields needed by the home feed renderer.
// Key parameter: unknown cached item; return value is a type guard.
function isTopicCard(value: unknown): value is TopicCardVM {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.id === "string" &&
    typeof value.slug === "string" &&
    typeof value.title === "string" &&
    typeof value.boardSlug === "string" &&
    typeof value.boardName === "string" &&
    typeof value.authorName === "string" &&
    Array.isArray(value.tags) &&
    typeof value.excerpt === "string" &&
    typeof value.replyCount === "number" &&
    typeof value.viewCount === "number" &&
    typeof value.lastPostedAt === "string"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
