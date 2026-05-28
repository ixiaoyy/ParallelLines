import type { PostItemVM } from "@/entities/post/model";

export interface PostResponse {
  id: string;
  topic_id: string;
  user_id: string;
  author_name: string;
  author_avatar_url?: string | null;
  author_role: string;
  author_level: number;
  author_trust_level: number;
  author_trust_level_label: string;
  parent_id: string | null;
  post_number: number;
  raw_md: string;
  cooked_html: string;
  reply_count: number;
  like_count: number;
  liked_by_me?: boolean;
  accepted_answer: boolean;
  vote_score: number;
  vote_count: number;
  my_vote: number;
  share_url: string;
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
  edit_reason?: string | null;
}

export interface RestorePostRevisionRequest {
  reason?: string | null;
}

export interface PostRevisionResponse {
  id: string;
  post_id: string;
  topic_id: string;
  version_number: number;
  editor_id: string | null;
  editor_name: string | null;
  raw_md: string;
  cooked_html: string;
  edit_reason: string | null;
  summary: string;
  restored_from_revision_id: string | null;
  created_at: string;
}

export interface PostRevisionVM {
  id: string;
  postId: string;
  topicId: string;
  versionNumber: number;
  editorId: string | null;
  editorName: string | null;
  rawMd: string;
  cookedHtml: string;
  editReason: string | null;
  summary: string;
  restoredFromRevisionId: string | null;
  createdAt: string;
}

export function toPostItem(post: PostResponse): PostItemVM {
  return {
    id: post.id,
    topicId: post.topic_id,
    userId: post.user_id,
    floor: post.post_number,
    authorName: post.author_name,
    authorAvatarUrl: post.author_avatar_url ?? null,
    authorRole: post.author_role,
    authorLevel: post.author_level,
    authorTrustLevel: post.author_trust_level,
    authorTrustLevelLabel: post.author_trust_level_label,
    createdAt: post.created_at,
    updatedAt: post.updated_at,
    rawMd: post.raw_md,
    cookedHtml: post.cooked_html,
    likeCount: post.like_count,
    likedByMe: Boolean(post.liked_by_me),
    acceptedAnswer: post.accepted_answer,
    voteScore: post.vote_score,
    voteCount: post.vote_count,
    myVote: post.my_vote,
    shareUrl: post.share_url,
    replyCount: post.reply_count,
    deleted: Boolean(post.deleted_at),
  };
}

export function toPostRevision(revision: PostRevisionResponse): PostRevisionVM {
  return {
    id: revision.id,
    postId: revision.post_id,
    topicId: revision.topic_id,
    versionNumber: revision.version_number,
    editorId: revision.editor_id,
    editorName: revision.editor_name,
    rawMd: revision.raw_md,
    cookedHtml: revision.cooked_html,
    editReason: revision.edit_reason,
    summary: revision.summary,
    restoredFromRevisionId: revision.restored_from_revision_id,
    createdAt: revision.created_at,
  };
}
