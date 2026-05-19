import type { BoardSummary } from "@/entities/board/model";
import type { TopicResponse } from "@/features/topics/model";

export interface BoardResponse {
  id: string;
  slug: string;
  name: string;
  description: string;
  color: string;
  avatar_url: string | null;
  owner_id: string | null;
  visibility: string;
  topic_count: number;
  post_count: number;
  follower_count: number;
  created_at: string;
  updated_at: string;
}

export interface BoardDetailResponse extends BoardResponse {
  latest_topics: TopicResponse[];
}

export function toBoardSummary(board: BoardResponse): BoardSummary {
  return {
    id: board.id,
    slug: board.slug,
    name: board.name,
    description: board.description,
    color: board.color,
    topicCount: board.topic_count,
    postCount: board.post_count,
    followerCount: board.follower_count,
    isFollowing: false,
  };
}
