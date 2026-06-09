import { apiGet, apiGetEnvelope, apiPost, apiPut } from "@/shared/api/client";

import type {
  CreateTopicRequest,
  ImmersiveTopicFeedItemResponse,
  ImmersiveTopicFeedPageResponse,
  ImmersiveTopicFeedParams,
  PollResponse,
  PollVoteRequest,
  TopicReadStateRequest,
  TopicReadStateResponse,
  TopicLifecycleRequest,
  TopicMoveRequest,
  TopicResponse,
  TopicSolutionRequest,
  TopicSort,
} from "./model";

export function fetchTopics(sort: TopicSort = "latest", limit = 30): Promise<TopicResponse[]> {
  return apiGet<TopicResponse[]>(`/topics?sort=${sort}&limit=${limit}`);
}

export interface TopicSearchParams {
  q: string;
  board?: string;
  tag?: string;
  author?: string;
  sort?: TopicSort;
  limit?: number;
}

export function searchTopics(params: TopicSearchParams): Promise<TopicResponse[]> {
  const query = new URLSearchParams({
    q: params.q,
    sort: params.sort ?? "latest",
    limit: String(params.limit ?? 50),
  });

  if (params.board) {
    query.set("board", params.board);
  }
  if (params.tag) {
    query.set("tag", params.tag);
  }
  if (params.author) {
    query.set("author", params.author);
  }

  return apiGet<TopicResponse[]>(`/search?${query.toString()}`);
}

export function fetchBoardTopics(
  boardSlug: string,
  sort: TopicSort = "latest",
  limit = 100,
): Promise<TopicResponse[]> {
  return apiGet<TopicResponse[]>(`/boards/${boardSlug}/topics?sort=${sort}&limit=${limit}`);
}

export function fetchTopic(topicId: string): Promise<TopicResponse> {
  return apiGet<TopicResponse>(`/topics/${topicId}`);
}

// Fetch one cursor page for the full-screen immersive topic feed.
// Key parameter `params` carries sort/filter/cursor options. Return value keeps
// feed rows plus `nextCursor`. Side effect: performs a GET request.
export async function fetchImmersiveTopicFeed(
  params: ImmersiveTopicFeedParams,
): Promise<ImmersiveTopicFeedPageResponse> {
  const query = new URLSearchParams({
    sort: params.sort ?? "latest",
    limit: String(params.limit ?? 20),
  });

  if (params.board) {
    query.set("board", params.board);
  }
  if (params.tag) {
    query.set("tag", params.tag);
  }
  if (params.q) {
    query.set("q", params.q);
  }
  if (params.author) {
    query.set("author", params.author);
  }
  if (params.cursor) {
    query.set("cursor", params.cursor);
  }

  const envelope = await apiGetEnvelope<ImmersiveTopicFeedItemResponse[]>(
    `/topics/immersive-feed?${query.toString()}`,
  );
  return {
    items: envelope.data,
    nextCursor: typeof envelope.meta?.next_cursor === "string" ? envelope.meta.next_cursor : null,
  };
}

// Persist the current user's read position for a topic.
// Key parameters are topic id and optional post number. Return value is the
// refreshed read state. Side effect: performs an authenticated PUT request.
export function markTopicReadState(
  topicId: string,
  payload: TopicReadStateRequest = {},
): Promise<TopicReadStateResponse> {
  return apiPut<TopicReadStateResponse, TopicReadStateRequest>(`/topics/${topicId}/read-state`, payload);
}

export function createTopic(boardSlug: string, payload: CreateTopicRequest): Promise<TopicResponse> {
  return apiPost<TopicResponse, CreateTopicRequest>(`/boards/${boardSlug}/topics`, payload);
}

export function updateTopicLifecycle(
  topicId: string,
  payload: TopicLifecycleRequest,
): Promise<TopicResponse> {
  return apiPut<TopicResponse, TopicLifecycleRequest>(`/topics/${topicId}/lifecycle`, payload);
}

export function moveTopic(topicId: string, payload: TopicMoveRequest): Promise<TopicResponse> {
  return apiPost<TopicResponse, TopicMoveRequest>(`/topics/${topicId}/move`, payload);
}

export function setTopicSolution(
  topicId: string,
  payload: TopicSolutionRequest,
): Promise<TopicResponse> {
  return apiPut<TopicResponse, TopicSolutionRequest>(`/topics/${topicId}/solution`, payload);
}

export function votePoll(topicId: string, payload: PollVoteRequest): Promise<PollResponse> {
  return apiPut<PollResponse, PollVoteRequest>(`/topics/${topicId}/poll/vote`, payload);
}
