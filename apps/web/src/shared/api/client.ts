export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export interface ApiEnvelope<T> {
  data: T;
  meta?: Record<string, unknown>;
}

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
    public status = 0,
  ) {
    super(message);
  }
}

interface ApiErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
}

interface RefreshAccessTokenResponse {
  access_token: string;
  token_type: string;
}

let refreshAccessTokenPromise: Promise<string | null> | null = null;

export function getApiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export function resolveApiAssetUrl(url: string): string;
export function resolveApiAssetUrl(url: null | undefined): undefined;
export function resolveApiAssetUrl(url: string | null | undefined): string | undefined;
export function resolveApiAssetUrl(url: string | null | undefined): string | undefined {
  if (!url) {
    return undefined;
  }

  if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:")) {
    return url;
  }

  if (url.startsWith("/uploads/")) {
    return getApiUrl(url);
  }

  if (url.startsWith("/api/v1/")) {
    const apiRoot = API_BASE_URL.replace(/\/api\/v1\/?$/, "");
    return `${apiRoot}${url}`;
  }

  return url;
}

export function getAccessToken(): string | null {
  return getStoredToken("parallellines.access_token", "access_token");
}

export function getRefreshToken(): string | null {
  return getStoredToken("parallellines.refresh_token", "refresh_token");
}

export function hasAccessToken(): boolean {
  return Boolean(getAccessToken());
}

export function setAuthTokens(accessToken: string, refreshToken: string): void {
  try {
    window.localStorage.setItem("parallellines.access_token", accessToken);
    window.localStorage.setItem("parallellines.refresh_token", refreshToken);
  } catch {
    // Ignore storage failures; callers will still see API errors if auth cannot persist.
  }
}

function setAccessToken(accessToken: string): void {
  try {
    window.localStorage.setItem("parallellines.access_token", accessToken);
  } catch {
    // Ignore storage failures; the retry will surface auth errors if persistence fails.
  }
}

export function clearAuthTokens(): void {
  try {
    window.localStorage.removeItem("parallellines.access_token");
    window.localStorage.removeItem("parallellines.refresh_token");
    window.localStorage.removeItem("access_token");
    window.localStorage.removeItem("refresh_token");
  } catch {
    // Ignore storage failures during logout.
  }
}

export function createApiHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  headers.set("Accept", "application/json");

  const token = getAccessToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return headers;
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const first = await performApiRequest(path, init);
  if (first.response.ok) {
    return unwrapApiResponse<T>(first.payload);
  }

  const firstError = toApiError(first.response, first.payload);
  if (shouldRefreshAfterFailure(path, first.response)) {
    const refreshedToken = await refreshAccessToken();
    if (refreshedToken) {
      const retry = await performApiRequest(path, init);
      if (retry.response.ok) {
        return unwrapApiResponse<T>(retry.payload);
      }
      throw toApiError(retry.response, retry.payload);
    }
  }

  throw firstError;
}

async function performApiRequest(
  path: string,
  init?: RequestInit,
): Promise<{ response: Response; payload: unknown }> {
  const headers = createApiHeaders(init?.headers);
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (init?.body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(getApiUrl(path), {
    ...init,
    headers,
  });

  return { response, payload: await readJsonPayload(response) };
}

async function refreshAccessToken(): Promise<string | null> {
  if (!refreshAccessTokenPromise) {
    refreshAccessTokenPromise = requestAccessTokenRefresh().finally(() => {
      refreshAccessTokenPromise = null;
    });
  }

  return refreshAccessTokenPromise;
}

async function requestAccessTokenRefresh(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return null;
  }

  try {
    const response = await fetch(getApiUrl("/auth/refresh"), {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    const payload = await readJsonPayload(response);
    if (!response.ok) {
      const error = toApiError(response, payload);
      if (isAuthenticationError(error) || error.code === "invalid_token") {
        clearAuthTokens();
        return null;
      }
      throw error;
    }

    const data = unwrapApiResponse<RefreshAccessTokenResponse>(payload);
    if (!data.access_token) {
      clearAuthTokens();
      return null;
    }

    setAccessToken(data.access_token);
    return data.access_token;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError("refresh_unavailable", "Session refresh unavailable", {}, 0);
  }
}

async function readJsonPayload(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return {};
  }
}

function unwrapApiResponse<T>(payload: unknown): T {
  return (payload as ApiEnvelope<T>).data;
}

function toApiError(response: Response, payload: unknown): ApiError {
  const error = (payload as ApiErrorEnvelope).error;
  return new ApiError(
    error?.code ?? "request_failed",
    error?.message ?? "Request failed",
    error?.details ?? {},
    response.status,
  );
}

function shouldRefreshAfterFailure(path: string, response: Response): boolean {
  return response.status === 401 && Boolean(getRefreshToken()) && !isRefreshExcludedPath(path);
}

function isRefreshExcludedPath(path: string): boolean {
  return (
    path === "/auth/refresh" ||
    path === "/auth/login" ||
    path === "/auth/register" ||
    path === "/auth/verify-email" ||
    path === "/auth/resend-verification" ||
    path === "/auth/2fa/verify-login" ||
    path.startsWith("/auth/password-reset/") ||
    path === "/auth/oauth/providers"
  );
}

function getStoredToken(primaryKey: string, legacyKey: string): string | null {
  try {
    return window.localStorage.getItem(primaryKey) ?? window.localStorage.getItem(legacyKey);
  } catch {
    return null;
  }
}

export function isAuthenticationError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  return apiRequest<T>(path, { ...init, method: "GET" });
}

export async function apiPut<T, TBody extends object>(
  path: string,
  body?: TBody,
  init?: RequestInit,
): Promise<T> {
  return apiRequest<T>(path, {
    ...init,
    method: "PUT",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export async function apiPatch<T, TBody extends object>(
  path: string,
  body?: TBody,
  init?: RequestInit,
): Promise<T> {
  return apiRequest<T>(path, {
    ...init,
    method: "PATCH",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export async function apiPost<T, TBody extends object>(
  path: string,
  body: TBody,
  init?: RequestInit,
): Promise<T> {
  return apiRequest<T>(path, {
    ...init,
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function apiDelete<T>(path: string, init?: RequestInit): Promise<T> {
  return apiRequest<T>(path, { ...init, method: "DELETE" });
}
