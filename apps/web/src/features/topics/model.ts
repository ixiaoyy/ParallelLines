import type { PostItemVM } from "@/entities/post/model";
import type { PollVM, TopicCardVM, TopicStatus } from "@/entities/topic/model";
import type { PostResponse } from "@/features/posts/model";
import { toPostItem } from "@/features/posts/model";
import { localizedText } from "@/shared/i18n/locale";

export type TopicSort = "latest" | "hot" | "top" | "votes";
export type ImmersiveTopicFeedSort = "latest" | "hot" | "top" | "votes" | "recommended";


export interface PollOptionResponse {
  id: string;
  label: string;
  position: number;
  vote_count: number;
}

export interface PollResponse {
  id: string;
  topic_id: string;
  question: string;
  multiple_choice: boolean;
  closes_at: string | null;
  closed: boolean;
  total_votes: number;
  selected_option_ids: string[];
  options: PollOptionResponse[];
  created_at: string;
  updated_at: string;
}

export interface PollCreateRequest {
  question: string;
  options: string[];
  multiple_choice?: boolean;
  closes_at?: string | null;
}

export interface TopicSolutionRequest {
  post_id: string | null;
}

export interface PollVoteRequest {
  option_ids: string[];
}

export interface TopicResponse {
  id: string;
  slug: string;
  title: string;
  title_localizations?: Record<string, string>;
  board_id: string;
  board_slug: string;
  board_name: string;
  board_color: string;
  author_id: string;
  author_name: string;
  author_avatar_url?: string | null;
  author_role: string;
  author_level: number;
  author_trust_level: number;
  author_trust_level_label: string;
  tags: string[];
  accepted_answer_post_id: string | null;
  solved_at: string | null;
  solved_by_id: string | null;
  answer_mode: boolean;
  vote_score: number;
  vote_count: number;
  my_vote: number;
  poll: PollResponse | null;
  topic_type: "regular" | "private_message" | (string & {});
  visibility: "public" | "private_message" | (string & {});
  status: string;
  pinned: boolean;
  featured: boolean;
  view_count: number;
  reply_count: number;
  like_count: number;
  liked_by_me?: boolean;
  bookmark_count?: number;
  bookmarked_by_me?: boolean;
  hot_score: number;
  last_posted_at: string;
  created_at: string;
  updated_at: string;
  merged_into_topic_id: string | null;
  share_url: string;
  excerpt: string;
}

export interface CreateTopicRequest {
  title: string;
  raw_md: string;
  tags: string[];
  pinned?: boolean;
  featured?: boolean;
  poll?: PollCreateRequest | null;
}

export interface TopicLifecycleRequest {
  status?: "open" | "closed" | "archived" | null;
  pinned?: boolean | null;
  note?: string | null;
}

export interface TopicMoveRequest {
  board_id?: string | null;
  board_slug?: string | null;
  note?: string | null;
}

export interface TopicReadStateRequest {
  last_read_post_number?: number | null;
}

export interface TopicReadStateResponse {
  topic_id: string;
  last_read_post_number: number;
  highest_post_number: number;
  unread_count: number;
  read: boolean;
  notification_level: "normal" | "tracking" | "watching" | "muted" | (string & {});
}

export interface ImmersiveTopicFeedItemResponse {
  topic: TopicResponse;
  lead_post: PostResponse | null;
  read_state: TopicReadStateResponse;
}

export interface ImmersiveTopicFeedPageResponse {
  items: ImmersiveTopicFeedItemResponse[];
  nextCursor: string | null;
}

export interface ImmersiveTopicFeedParams {
  sort?: ImmersiveTopicFeedSort;
  board?: string;
  tag?: string;
  q?: string;
  author?: string;
  cursor?: string | null;
  limit?: number;
}

export interface ImmersiveTopicFeedItemVM {
  topic: TopicCardVM;
  leadPost: PostItemVM | null;
  readState: TopicReadStateResponse;
}

export function toTopicCard(topic: TopicResponse): TopicCardVM {
  return {
    id: topic.id,
    slug: topic.slug,
    title: localizedText(topic.title_localizations, topic.title),
    boardSlug: topic.board_slug,
    boardName: topic.board_name,
    boardColor: topic.board_color,
    authorId: topic.author_id,
    authorName: topic.author_name,
    authorAvatarUrl: topic.author_avatar_url ?? null,
    authorRole: topic.author_role,
    authorLevel: topic.author_level,
    authorTrustLevel: topic.author_trust_level,
    authorTrustLevelLabel: topic.author_trust_level_label,
    posterNames: [topic.author_name],
    tags: topic.tags,
    excerpt: topic.excerpt,
    replyCount: topic.reply_count,
    viewCount: topic.view_count,
    likeCount: topic.like_count,
    likedByMe: Boolean(topic.liked_by_me),
    bookmarkCount: topic.bookmark_count ?? 0,
    bookmarkedByMe: Boolean(topic.bookmarked_by_me),
    voteScore: topic.vote_score,
    voteCount: topic.vote_count,
    myVote: topic.my_vote,
    hotScore: topic.hot_score,
    lastPostedAt: topic.last_posted_at,
    pinned: topic.pinned,
    featured: topic.featured,
    officialReply: topic.featured,
    solved: Boolean(topic.accepted_answer_post_id),
    acceptedAnswerPostId: topic.accepted_answer_post_id,
    solvedAt: topic.solved_at,
    poll: topic.poll ? toPollVM(topic.poll) : null,
    status: normalizeTopicStatus(topic.status),
    shareUrl: topic.share_url,
  };
}

// Convert an immersive API row into the feed page view model.
// Key parameter `item` is one backend feed response. Return value localizes the
// topic and maps the lead post if present. Side effect: none.
export function toImmersiveTopicFeedItem(
  item: ImmersiveTopicFeedItemResponse,
): ImmersiveTopicFeedItemVM {
  return {
    topic: toTopicCard(item.topic),
    leadPost: item.lead_post ? toPostItem(item.lead_post) : null,
    readState: item.read_state,
  };
}

function normalizeTopicStatus(value: string): TopicStatus {
  if (value === "closed" || value === "archived" || value === "hidden") {
    return value;
  }

  return "open";
}


export function toPollVM(poll: PollResponse): PollVM {
  return {
    id: poll.id,
    topicId: poll.topic_id,
    question: poll.question,
    multipleChoice: poll.multiple_choice,
    closesAt: poll.closes_at,
    closed: poll.closed,
    totalVotes: poll.total_votes,
    selectedOptionIds: poll.selected_option_ids,
    options: poll.options.map((option) => ({
      id: option.id,
      label: option.label,
      position: option.position,
      voteCount: option.vote_count,
    })),
  };
}
