export type TopicStatus = "open" | "closed" | "archived" | "hidden";

export interface TopicCardVM {
  id: string;
  slug: string;
  title: string;
  boardName: string;
  authorName: string;
  tags: string[];
  excerpt: string;
  replyCount: number;
  viewCount: number;
  hotScore: number;
  lastPostedAt: string;
  pinned?: boolean;
  featured?: boolean;
  status: TopicStatus;
}
