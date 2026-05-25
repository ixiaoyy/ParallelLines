export type BoardNotificationLevel = "muted" | "normal" | "tracking" | "watching";
export type BoardDefaultSort = "latest" | "hot" | "top";

export interface BoardSummary {
  id: string;
  slug: string;
  name: string;
  description: string;
  color: string;
  ownerId: string | null;
  parentBoardId: string | null;
  parentBoardSlug: string | null;
  parentBoardName: string | null;
  visibility: string;
  requiredTags: string[];
  allowedTags: string[];
  postTemplate: string | null;
  defaultNotificationLevel: BoardNotificationLevel;
  defaultSort: BoardDefaultSort;
  topicCount: number;
  postCount: number;
  followerCount: number;
  isFollowing: boolean;
  notificationLevel: BoardNotificationLevel | null;
}
