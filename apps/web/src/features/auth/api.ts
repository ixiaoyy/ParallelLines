import { apiDelete, apiGet, apiPost } from "@/shared/api/client";

import type {
  ChangePasswordRequest,
  EmailChangeConfirmRequest,
  EmailChangeRequest,
  EmailChangeStartResponse,
  LoginResponse,
  LoginRequest,
  OAuthProviderResponse,
  PasswordResetConfirmRequest,
  PasswordResetRequest,
  PasswordResetStartResponse,
  RegistrationStartResponse,
  RegisterRequest,
  ResendVerificationRequest,
  SessionResponse,
  TokenPair,
  TwoFactorDisableRequest,
  TwoFactorEnableRequest,
  TwoFactorLoginVerifyRequest,
  TwoFactorRecoveryCodesResponse,
  TwoFactorSetupRequest,
  TwoFactorSetupResponse,
  UserPublic,
  VerifyEmailRequest,
} from "./model";

export function login(payload: LoginRequest): Promise<LoginResponse> {
  return apiPost<LoginResponse, LoginRequest>("/auth/login", payload);
}

export function register(payload: RegisterRequest): Promise<RegistrationStartResponse> {
  return apiPost<RegistrationStartResponse, RegisterRequest>("/auth/register", payload);
}

export function verifyEmail(payload: VerifyEmailRequest): Promise<TokenPair> {
  return apiPost<TokenPair, VerifyEmailRequest>("/auth/verify-email", payload);
}

export function resendVerification(
  payload: ResendVerificationRequest,
): Promise<RegistrationStartResponse> {
  return apiPost<RegistrationStartResponse, ResendVerificationRequest>(
    "/auth/resend-verification",
    payload,
  );
}

export function fetchCurrentUser(): Promise<UserPublic> {
  return apiGet<UserPublic>("/auth/me");
}

export function verifyTwoFactorLogin(payload: TwoFactorLoginVerifyRequest): Promise<TokenPair> {
  return apiPost<TokenPair, TwoFactorLoginVerifyRequest>("/auth/2fa/verify-login", payload);
}

export function requestPasswordReset(
  payload: PasswordResetRequest,
): Promise<PasswordResetStartResponse> {
  return apiPost<PasswordResetStartResponse, PasswordResetRequest>(
    "/auth/password-reset/request",
    payload,
  );
}

export function confirmPasswordReset(
  payload: PasswordResetConfirmRequest,
): Promise<Record<string, boolean>> {
  return apiPost<Record<string, boolean>, PasswordResetConfirmRequest>(
    "/auth/password-reset/confirm",
    payload,
  );
}

export function changePassword(payload: ChangePasswordRequest): Promise<Record<string, boolean>> {
  return apiPost<Record<string, boolean>, ChangePasswordRequest>("/auth/password/change", payload);
}

export function requestEmailChange(
  payload: EmailChangeRequest,
): Promise<EmailChangeStartResponse> {
  return apiPost<EmailChangeStartResponse, EmailChangeRequest>(
    "/auth/email-change/request",
    payload,
  );
}

export function confirmEmailChange(payload: EmailChangeConfirmRequest): Promise<UserPublic> {
  return apiPost<UserPublic, EmailChangeConfirmRequest>("/auth/email-change/confirm", payload);
}

export function setupTwoFactor(payload: TwoFactorSetupRequest): Promise<TwoFactorSetupResponse> {
  return apiPost<TwoFactorSetupResponse, TwoFactorSetupRequest>("/auth/2fa/setup", payload);
}

export function enableTwoFactor(
  payload: TwoFactorEnableRequest,
): Promise<TwoFactorRecoveryCodesResponse> {
  return apiPost<TwoFactorRecoveryCodesResponse, TwoFactorEnableRequest>(
    "/auth/2fa/enable",
    payload,
  );
}

export function disableTwoFactor(payload: TwoFactorDisableRequest): Promise<Record<string, boolean>> {
  return apiPost<Record<string, boolean>, TwoFactorDisableRequest>("/auth/2fa/disable", payload);
}

export function regenerateRecoveryCodes(
  payload: TwoFactorDisableRequest,
): Promise<TwoFactorRecoveryCodesResponse> {
  return apiPost<TwoFactorRecoveryCodesResponse, TwoFactorDisableRequest>(
    "/auth/2fa/recovery-codes",
    payload,
  );
}

export function fetchSessions(): Promise<SessionResponse[]> {
  return apiGet<SessionResponse[]>("/auth/sessions");
}

export function revokeSession(sessionId: string): Promise<Record<string, boolean>> {
  return apiDelete<Record<string, boolean>>(`/auth/sessions/${sessionId}`);
}

export function revokeOtherSessions(): Promise<Record<string, number>> {
  return apiPost<Record<string, number>, Record<string, never>>("/auth/sessions/revoke-others", {});
}

export function fetchOAuthProviders(): Promise<OAuthProviderResponse> {
  return apiGet<OAuthProviderResponse>("/auth/oauth/providers");
}

export function logout(): Promise<Record<string, boolean>> {
  return apiPost<Record<string, boolean>, Record<string, never>>("/auth/logout", {});
}
