import type { BoardDefaultSort, BoardNotificationLevel, BoardSummary } from "@/entities/board/model";
import type { TopicResponse } from "@/features/topics/model";
import { localizedText } from "@/shared/i18n/locale";

export interface BoardResponse {
  id: string;
  slug: string;
  name: string;
  name_localizations?: Record<string, string>;
  description: string;
  color: string;
  avatar_url: string | null;
  owner_id: string | null;
  parent_board_id: string | null;
  parent_board_slug: string | null;
  parent_board_name: string | null;
  visibility: string;
  required_tags: string[];
  allowed_tags: string[];
  post_template: string | null;
  default_notification_level: BoardNotificationLevel;
  default_sort: BoardDefaultSort;
  topic_count: number;
  post_count: number;
  follower_count: number;
  is_following: boolean;
  notification_level: BoardNotificationLevel | null;
  created_at: string;
  updated_at: string;
}

export interface BoardDetailResponse extends BoardResponse {
  latest_topics: TopicResponse[];
  child_boards: BoardResponse[];
}

export interface BoardMemberResponse {
  user_id: string;
  username: string;
  role: "owner" | "moderator" | "follower" | (string & {});
  notification_level: BoardNotificationLevel;
  joined_at: string;
}

export interface BoardSettingsResponse {
  board: BoardResponse;
  members: BoardMemberResponse[];
}

export interface BoardSettingsUpdateRequest {
  parent_board_id?: string | null;
  parent_board_slug?: string | null;
  required_tags: string[];
  allowed_tags: string[];
  post_template?: string | null;
  default_notification_level: BoardNotificationLevel;
  default_sort: BoardDefaultSort;
}

export interface BoardMemberUpdateRequest {
  role: "follower" | "moderator";
  notification_level?: BoardNotificationLevel | null;
}

export interface BoardMemberRemoveResponse {
  board_id: string;
  username: string;
  removed: boolean;
}

export function toBoardSummary(board: BoardResponse): BoardSummary {
  return {
    id: board.id,
    slug: board.slug,
    name: localizedText(board.name_localizations, board.name),
    description: board.description,
    color: board.color,
    ownerId: board.owner_id,
    parentBoardId: board.parent_board_id,
    parentBoardSlug: board.parent_board_slug,
    parentBoardName: board.parent_board_name,
    visibility: board.visibility,
    requiredTags: board.required_tags ?? [],
    allowedTags: board.allowed_tags ?? [],
    postTemplate: board.post_template,
    defaultNotificationLevel: board.default_notification_level,
    defaultSort: board.default_sort,
    topicCount: board.topic_count,
    postCount: board.post_count,
    followerCount: board.follower_count,
    isFollowing: board.is_following,
    notificationLevel: board.notification_level,
  };
}
