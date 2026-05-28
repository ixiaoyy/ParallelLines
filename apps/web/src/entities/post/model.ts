export interface PostItemVM {
  id: string;
  topicId: string;
  userId: string;
  floor: number;
  authorName: string;
  authorAvatarUrl: string | null;
  authorRole: string;
  authorLevel: number;
  authorTrustLevel: number;
  authorTrustLevelLabel: string;
  createdAt: string;
  updatedAt: string;
  rawMd: string;
  cookedHtml: string;
  likeCount: number;
  likedByMe: boolean;
  replyCount: number;
  acceptedAnswer: boolean;
  voteScore: number;
  voteCount: number;
  myVote: number;
  shareUrl: string;
  deleted?: boolean;
}
