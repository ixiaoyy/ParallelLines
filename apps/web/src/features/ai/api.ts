import { apiGet, apiPost } from "@/shared/api/client";

import type {
  ModerationAdvice,
  ModerationAdviceRequest,
  SimilarTopic,
  SimilarTopicsRequest,
  TopicAiSummary,
} from "./model";

export function fetchTopicAiSummary(topicId: string): Promise<TopicAiSummary> {
  return apiGet<TopicAiSummary>(`/topics/${topicId}/ai-summary`);
}

export function refreshTopicAiSummary(topicId: string): Promise<TopicAiSummary> {
  return apiPost<TopicAiSummary, Record<string, never>>(
    `/topics/${topicId}/ai-summary/refresh`,
    {},
  );
}

export function fetchSimilarTopics(payload: SimilarTopicsRequest): Promise<SimilarTopic[]> {
  return apiPost<SimilarTopic[], SimilarTopicsRequest>("/ai/similar-topics", payload);
}

export function fetchModerationAdvice(
  payload: ModerationAdviceRequest,
): Promise<ModerationAdvice> {
  return apiPost<ModerationAdvice, ModerationAdviceRequest>("/ai/moderation-advice", payload);
}
