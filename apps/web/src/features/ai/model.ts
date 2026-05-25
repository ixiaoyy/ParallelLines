export interface TopicAiSummary {
  topic_id: string;
  summary: string;
  key_points: string[];
  key_post_ids: string[];
  model_name: string;
  cost_units: number;
  refreshed_by_id: string | null;
  generated_at: string;
  updated_at: string;
}

export interface SimilarTopicsRequest {
  title: string;
  raw_md: string;
  tags: string[];
  limit?: number;
}

export interface SimilarTopic {
  id: string;
  title: string;
  slug: string;
  board_slug: string;
  board_name: string;
  score: number;
  matched_terms: string[];
  excerpt: string;
}

export interface ModerationAdviceRequest {
  target_type?: string;
  title?: string | null;
  raw_text: string;
  reason?: string | null;
}

export interface ModerationAdvice {
  risk_level: "low" | "medium" | "high";
  summary: string;
  reasons: string[];
  suggested_actions: string[];
  requires_human_review: boolean;
  auto_action_allowed: boolean;
  cost_units: number;
}
