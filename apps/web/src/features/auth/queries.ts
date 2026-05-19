import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { clearAuthTokens, hasAccessToken, setAuthTokens } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import { fetchCurrentUser, login, register } from "./api";
import type { LoginRequest, RegisterRequest, TokenPair, UserPublic } from "./model";

export function useCurrentUser() {
  return useQuery<UserPublic | null, Error>({
    queryKey: queryKeys.currentUser,
    queryFn: async () => {
      if (!hasAccessToken()) {
        return null;
      }

      try {
        return await fetchCurrentUser();
      } catch {
        clearAuthTokens();
        return null;
      }
    },
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogin() {
  return useAuthMutation(login);
}

export function useRegister() {
  return useAuthMutation(register);
}

export function useLogout() {
  const queryClient = useQueryClient();

  return async () => {
    clearAuthTokens();
    queryClient.setQueryData(queryKeys.currentUser, null);
    await queryClient.invalidateQueries({ queryKey: queryKeys.auth });
  };
}

function useAuthMutation<TPayload extends LoginRequest | RegisterRequest>(
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
