import type { UserRole, UserStatus } from "@/features/auth/model";

export interface UserProfile {
  id: string;
  username: string;
  avatar_url: string | null;
  role: UserRole;
  status: UserStatus;
  created_at: string;
  topic_count: number;
  post_count: number;
}
