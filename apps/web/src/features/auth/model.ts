export type UserRole = "user" | "moderator" | "admin" | string;
export type UserStatus = "active" | "silenced" | "suspended" | "deleted" | string;

export const CURRENT_USER_STALE_TIME_MS = 5 * 60_000;

export interface UserPublic {
  id: string;
  username: string;
  email: string;
  avatar_url: string | null;
  display_name: string | null;
  bio: string | null;
  website_url: string | null;
  location: string | null;
  role: UserRole;
  level: number;
  trust_level: number;
  trust_level_label: string;
  points_balance: number;
  experience_total: number;
  experience_to_next_level: number;
  level_progress_percent: number;
  status: UserStatus;
  two_factor_enabled: boolean;
  profile_visibility: "public" | "members" | "private" | string;
  show_activity: boolean;
  interface_theme: "system" | "light" | "colorful" | string;
  locale: "zh-CN" | "en-US" | string;
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

export interface RegistrationStartResponse {
  email: string;
  verification_required: true;
  expires_in_seconds: number;
  resend_after_seconds: number;
  dev_verification_code: string | null;
}

export interface VerifyEmailRequest {
  email: string;
  code: string;
}

export interface ResendVerificationRequest {
  email: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer" | string;
  user: UserPublic;
  session_id: string | null;
}

export interface LoginResponse {
  access_token: string | null;
  refresh_token: string | null;
  token_type: "bearer" | string;
  user: UserPublic | null;
  session_id: string | null;
  two_factor_required: boolean;
  challenge_token: string | null;
}

export interface TwoFactorLoginVerifyRequest {
  challenge_token: string;
  code: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetStartResponse {
  ok: true;
  expires_in_seconds: number;
}

export interface PasswordResetConfirmRequest {
  email: string;
  token: string;
  new_password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface EmailChangeRequest {
  new_email: string;
  password: string;
}

export interface EmailChangeStartResponse {
  email: string;
  expires_in_seconds: number;
}

export interface EmailChangeConfirmRequest {
  token: string;
}

export interface TwoFactorSetupRequest {
  password: string;
}

export interface TwoFactorSetupResponse {
  secret: string;
  otpauth_url: string;
}

export interface TwoFactorEnableRequest {
  secret: string;
  code: string;
}

export interface TwoFactorDisableRequest {
  password: string;
  code: string;
}

export interface TwoFactorRecoveryCodesResponse {
  recovery_codes: string[];
}

export interface SessionResponse {
  id: string;
  user_agent: string | null;
  ip_address: string | null;
  current: boolean;
  created_at: string;
  last_seen_at: string;
  revoked_at: string | null;
}

export interface OAuthProviderResponse {
  providers: string[];
}
