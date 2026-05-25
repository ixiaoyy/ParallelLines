export type TopicStatus = "open" | "closed" | "archived" | "hidden";

export interface TopicCardVM {
  id: string;
  slug: string;
  title: string;
  boardSlug: string;
  boardName: string;
  boardColor: string;
  authorId: string;
  authorName: string;
  authorLevel: number;
  authorTrustLevel: number;
  authorTrustLevelLabel: string;
  posterNames: string[];
  tags: string[];
  excerpt: string;
  replyCount: number;
  viewCount: number;
  likeCount: number;
  likedByMe: boolean;
  bookmarkCount: number;
  bookmarkedByMe: boolean;
  voteScore: number;
  voteCount: number;
  myVote: number;
  hotScore: number;
  lastPostedAt: string;
  pinned?: boolean;
  featured?: boolean;
  solved?: boolean;
  acceptedAnswerPostId?: string | null;
  solvedAt?: string | null;
  officialReply?: boolean;
  unreadCount?: number;
  status: TopicStatus;
  shareUrl: string;
  poll?: PollVM | null;
}

export interface PollOptionVM {
  id: string;
  label: string;
  position: number;
  voteCount: number;
}

export interface PollVM {
  id: string;
  topicId: string;
  question: string;
  multipleChoice: boolean;
  closesAt: string | null;
  closed: boolean;
  totalVotes: number;
  selectedOptionIds: string[];
  options: PollOptionVM[];
}
