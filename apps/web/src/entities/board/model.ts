export interface BoardSummary {
  id: string;
  slug: string;
  name: string;
  description: string;
  color: string;
  visibility: string;
  topicCount: number;
  postCount: number;
  followerCount: number;
  isFollowing: boolean;
}
