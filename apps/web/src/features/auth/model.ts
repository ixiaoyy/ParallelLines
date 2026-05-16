export type UserRole = "user" | "moderator" | "admin" | string;
export type UserStatus = "active" | "silenced" | "suspended" | "deleted" | string;

export interface UserPublic {
  id: string;
  username: string;
  email: string;
  avatar_url: string | null;
  role: UserRole;
  status: UserStatus;
  created_at: string;
}

export interface LoginRequest {
  account: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer" | string;
  user: UserPublic;
}
