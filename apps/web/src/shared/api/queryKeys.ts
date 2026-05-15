export const queryKeys = {
  boards: ["boards"] as const,
  board: (slug: string) => ["boards", slug] as const,
  topics: (filter: string) => ["topics", filter] as const,
  topic: (id: string) => ["topics", "detail", id] as const,
  posts: (topicId: string) => ["topics", "posts", topicId] as const,
  notifications: ["notifications"] as const,
  moderationRoot: ["moderation"] as const,
  moderationQueue: (status: string) => ["moderation", "queue", status] as const,
  moderationAudit: ["moderation", "audit"] as const,
};
