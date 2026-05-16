import type { PostItemVM } from "@/entities/post/model";

export interface PostResponse {
  id: string;
  topic_id: string;
  user_id: string;
  author_name: string;
  parent_id: string | null;
  post_number: number;
  raw_md: string;
  cooked_html: string;
  reply_count: number;
  like_count: number;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreatePostRequest {
  raw_md: string;
  parent_post_id?: string | null;
}

export interface UpdatePostRequest {
  raw_md: string;
}

export function toPostItem(post: PostResponse): PostItemVM {
  return {
    id: post.id,
    topicId: post.topic_id,
    userId: post.user_id,
    floor: post.post_number,
    authorName: post.author_name,
    createdAt: post.created_at,
    updatedAt: post.updated_at,
    rawMd: post.raw_md,
    cookedHtml: post.cooked_html,
    likeCount: post.like_count,
    replyCount: post.reply_count,
    deleted: Boolean(post.deleted_at),
  };
}
