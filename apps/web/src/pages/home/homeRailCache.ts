import type { BoardSummary } from "@/entities/board/model";
import type { TagItemVM } from "@/features/tags/model";
import { hasAccessToken } from "@/shared/api/client";
import { readPersistentCache, writePersistentCache } from "@/shared/lib/persistentCache";

const CACHE_TTL_MS = 10 * 60 * 1000;
const PUBLIC_BOARDS_CACHE_KEY = "parallellines.homeRail.publicBoards.v1";
const PUBLIC_TAGS_CACHE_KEY = "parallellines.homeRail.publicTags.v1";

export function readCachedHomeRailBoards(): BoardSummary[] {
  return readPersistentCache(PUBLIC_BOARDS_CACHE_KEY, isBoardSummaryArray, CACHE_TTL_MS) ?? [];
}

export function readCachedHomeRailTags(): TagItemVM[] {
  return readPersistentCache(PUBLIC_TAGS_CACHE_KEY, isTagItemArray, CACHE_TTL_MS) ?? [];
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
  if (!publicTags.length || hasAccessToken()) {
    return publicTags;
  }

  writePersistentCache(PUBLIC_TAGS_CACHE_KEY, publicTags);
  return publicTags;
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
