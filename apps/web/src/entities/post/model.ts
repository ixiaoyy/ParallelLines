export interface PostItemVM {
  id: string;
  topicId: string;
  userId: string;
  floor: number;
  authorName: string;
  createdAt: string;
  updatedAt: string;
  rawMd: string;
  cookedHtml: string;
  likeCount: number;
  replyCount: number;
  deleted?: boolean;
}
