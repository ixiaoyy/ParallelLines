export const queryKeys = {
  boards: ["boards"] as const,
  topics: (filter: string) => ["topics", filter] as const,
  notifications: ["notifications"] as const,
};
