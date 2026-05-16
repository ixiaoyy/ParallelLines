import { apiGet, apiPost } from "@/shared/api/client";

import type { LoginRequest, RegisterRequest, TokenPair, UserPublic } from "./model";

export function login(payload: LoginRequest): Promise<TokenPair> {
  return apiPost<TokenPair, LoginRequest>("/auth/login", payload);
}

export function register(payload: RegisterRequest): Promise<TokenPair> {
  return apiPost<TokenPair, RegisterRequest>("/auth/register", payload);
}

export function fetchCurrentUser(): Promise<UserPublic> {
  return apiGet<UserPublic>("/auth/me");
}
