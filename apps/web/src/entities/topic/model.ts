export type TopicStatus = "open" | "closed" | "archived" | "hidden";

export interface TopicCardVM {
  id: string;
  slug: string;
  title: string;
  boardName: string;
  boardColor: string;
  authorName: string;
  posterNames: string[];
  tags: string[];
  excerpt: string;
  replyCount: number;
  viewCount: number;
  likeCount: number;
  hotScore: number;
  lastPostedAt: string;
  pinned?: boolean;
  featured?: boolean;
  solved?: boolean;
  unreadCount?: number;
  status: TopicStatus;
}
