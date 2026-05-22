import type { TopicCardVM, TopicStatus } from "@/entities/topic/model";

export type TopicSort = "latest" | "hot" | "top";

export interface TopicResponse {
  id: string;
  slug: string;
  title: string;
  board_id: string;
  board_slug: string;
  board_name: string;
  board_color: string;
  author_id: string;
  author_name: string;
  tags: string[];
  topic_type: "regular" | "private_message" | (string & {});
  visibility: "public" | "private_message" | (string & {});
  status: string;
  pinned: boolean;
  featured: boolean;
  view_count: number;
  reply_count: number;
  like_count: number;
  hot_score: number;
  last_posted_at: string;
  created_at: string;
  updated_at: string;
  merged_into_topic_id: string | null;
  excerpt: string;
}

export interface CreateTopicRequest {
  title: string;
  raw_md: string;
  tags: string[];
  pinned?: boolean;
  featured?: boolean;
}

export interface TopicLifecycleRequest {
  status?: "open" | "closed" | "archived" | null;
  pinned?: boolean | null;
  note?: string | null;
}

export interface TopicMoveRequest {
  board_id?: string | null;
  board_slug?: string | null;
  note?: string | null;
}

export interface TopicSplitRequest {
  title: string;
  post_ids: string[];
  board_id?: string | null;
  board_slug?: string | null;
  note?: string | null;
}

export interface TopicMergeRequest {
  target_topic_id: string;
  note?: string | null;
}

export interface TopicLifecycleResponse {
  source_topic: TopicResponse | null;
  target_topic: TopicResponse;
  moved_post_count: number;
  audit_action: string;
}

export function toTopicCard(topic: TopicResponse): TopicCardVM {
  return {
    id: topic.id,
    slug: topic.slug,
    title: topic.title,
    boardSlug: topic.board_slug,
    boardName: topic.board_name,
    boardColor: topic.board_color,
    authorName: topic.author_name,
    posterNames: [topic.author_name],
    tags: topic.tags,
    excerpt: topic.excerpt,
    replyCount: topic.reply_count,
    viewCount: topic.view_count,
    likeCount: topic.like_count,
    hotScore: topic.hot_score,
    lastPostedAt: topic.last_posted_at,
    pinned: topic.pinned,
    featured: topic.featured,
    officialReply: topic.featured,
    solved: topic.tags.some((tag) => ["已解决", "solved", "solution"].includes(tag.toLocaleLowerCase())),
    status: normalizeTopicStatus(topic.status),
  };
}

function normalizeTopicStatus(value: string): TopicStatus {
  if (value === "closed" || value === "archived" || value === "hidden") {
    return value;
  }

  return "open";
}
