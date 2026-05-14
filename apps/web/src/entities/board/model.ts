export interface BoardSummary {
  id: string;
  slug: string;
  name: string;
  description: string;
  color: string;
  topicCount: number;
  postCount: number;
  followerCount: number;
  isFollowing: boolean;
}
