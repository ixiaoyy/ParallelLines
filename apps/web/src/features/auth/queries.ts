import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import {
  clearAuthTokens,
  hasAccessToken,
  isAuthenticationError,
  setAuthTokens,
} from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  changePassword,
  confirmEmailChange,
  confirmPasswordReset,
  disableTwoFactor,
  enableTwoFactor,
  fetchCurrentUser,
  fetchOAuthProviders,
  fetchSessions,
  login,
  logout,
  register,
  regenerateRecoveryCodes,
  requestEmailChange,
  requestPasswordReset,
  resendVerification,
  revokeOtherSessions,
  revokeSession,
  setupTwoFactor,
  verifyEmail,
  verifyTwoFactorLogin,
} from "./api";
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

export function useCurrentUser() {
  return useQuery<UserPublic | null, Error>({
    queryKey: queryKeys.currentUser,
    queryFn: async () => {
      if (!hasAccessToken()) {
        return null;
      }

      try {
        return await fetchCurrentUser();
      } catch (error) {
        if (isAuthenticationError(error)) {
          clearAuthTokens();
          return null;
        }

        throw error;
      }
    },
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation<LoginResponse, Error, LoginRequest>({
    mutationFn: login,
    onSuccess: async (response) => {
      if (response.two_factor_required) {
        return;
      }

      if (response.access_token && response.refresh_token && response.user) {
        setAuthTokens(response.access_token, response.refresh_token);
        queryClient.setQueryData(queryKeys.currentUser, response.user);
        await queryClient.invalidateQueries({ queryKey: queryKeys.auth });
      }
    },
  });
}

export function useRegister() {
  return useMutation<RegistrationStartResponse, Error, RegisterRequest>({
    mutationFn: register,
  });
}

export function useVerifyEmail() {
  return useTokenPairMutation<VerifyEmailRequest>(verifyEmail);
}

export function useVerifyTwoFactorLogin() {
  return useTokenPairMutation<TwoFactorLoginVerifyRequest>(verifyTwoFactorLogin);
}

export function useResendVerification() {
  return useMutation<RegistrationStartResponse, Error, ResendVerificationRequest>({
    mutationFn: resendVerification,
  });
}

export function useLogout() {
  const queryClient = useQueryClient();

  return async () => {
    if (hasAccessToken()) {
      try {
        await logout();
      } catch {
        // Local logout must still clear credentials if the server session already expired.
      }
    }

    clearAuthTokens();
    queryClient.setQueryData(queryKeys.currentUser, null);
    await queryClient.invalidateQueries({ queryKey: queryKeys.auth });
  };
}

export function useRequestPasswordReset() {
  return useMutation<PasswordResetStartResponse, Error, PasswordResetRequest>({
    mutationFn: requestPasswordReset,
  });
}

export function useConfirmPasswordReset() {
  return useMutation<Record<string, boolean>, Error, PasswordResetConfirmRequest>({
    mutationFn: confirmPasswordReset,
  });
}

export function useChangePassword() {
  const queryClient = useQueryClient();

  return useMutation<Record<string, boolean>, Error, ChangePasswordRequest>({
    mutationFn: changePassword,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
    },
  });
}

export function useRequestEmailChange() {
  return useMutation<EmailChangeStartResponse, Error, EmailChangeRequest>({
    mutationFn: requestEmailChange,
  });
}

export function useConfirmEmailChange() {
  const queryClient = useQueryClient();

  return useMutation<UserPublic, Error, EmailChangeConfirmRequest>({
    mutationFn: confirmEmailChange,
    onSuccess: (user) => {
      queryClient.setQueryData(queryKeys.currentUser, user);
    },
  });
}

export function useTwoFactorSetup() {
  return useMutation<TwoFactorSetupResponse, Error, TwoFactorSetupRequest>({
    mutationFn: setupTwoFactor,
  });
}

export function useTwoFactorEnable() {
  const queryClient = useQueryClient();

  return useMutation<TwoFactorRecoveryCodesResponse, Error, TwoFactorEnableRequest>({
    mutationFn: enableTwoFactor,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.currentUser });
    },
  });
}

export function useTwoFactorDisable() {
  const queryClient = useQueryClient();

  return useMutation<Record<string, boolean>, Error, TwoFactorDisableRequest>({
    mutationFn: disableTwoFactor,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.currentUser });
    },
  });
}

export function useRegenerateRecoveryCodes() {
  return useMutation<TwoFactorRecoveryCodesResponse, Error, TwoFactorDisableRequest>({
    mutationFn: regenerateRecoveryCodes,
  });
}

export function useSessions() {
  return useQuery<SessionResponse[], Error>({
    queryKey: queryKeys.sessions,
    queryFn: fetchSessions,
    enabled: hasAccessToken(),
    retry: false,
  });
}

export function useRevokeSession() {
  const queryClient = useQueryClient();

  return useMutation<Record<string, boolean>, Error, string>({
    mutationFn: revokeSession,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
    },
  });
}

export function useRevokeOtherSessions() {
  const queryClient = useQueryClient();

  return useMutation<Record<string, number>, Error, void>({
    mutationFn: revokeOtherSessions,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.sessions });
    },
  });
}

export function useOAuthProviders() {
  return useQuery<OAuthProviderResponse, Error>({
    queryKey: queryKeys.oauthProviders,
    queryFn: fetchOAuthProviders,
    staleTime: 300_000,
  });
}

function useTokenPairMutation<TPayload>(
  mutationFn: (payload: TPayload) => Promise<TokenPair>,
) {
  const queryClient = useQueryClient();

  return useMutation<TokenPair, Error, TPayload>({
    mutationFn,
    onSuccess: async (tokenPair) => {
      setAuthTokens(tokenPair.access_token, tokenPair.refresh_token);
      queryClient.setQueryData(queryKeys.currentUser, tokenPair.user);
      await queryClient.invalidateQueries({ queryKey: queryKeys.auth });
    },
  });
}
