export interface PostItemVM {
  id: string;
  floor: number;
  authorName: string;
  createdAt: string;
  cookedHtml: string;
  likeCount: number;
  replyCount: number;
  deleted?: boolean;
}
