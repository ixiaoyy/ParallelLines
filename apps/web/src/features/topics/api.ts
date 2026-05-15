import { apiGet, apiPost } from "@/shared/api/client";

import type { CreateTopicRequest, TopicResponse, TopicSort } from "./model";

export function fetchTopics(sort: TopicSort = "latest", limit = 50): Promise<TopicResponse[]> {
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

export function createTopic(boardSlug: string, payload: CreateTopicRequest): Promise<TopicResponse> {
  return apiPost<TopicResponse, CreateTopicRequest>(`/boards/${boardSlug}/topics`, payload);
}
