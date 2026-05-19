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
  ) {
    super(message);
  }
}

export function getApiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export function getAccessToken(): string | null {
  try {
    return (
      window.localStorage.getItem("parallellines.access_token") ??
      window.localStorage.getItem("access_token")
    );
  } catch {
    return null;
  }
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
  const headers = createApiHeaders(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(getApiUrl(path), {
    ...init,
    headers,
  });
  const payload = await response.json();

  if (!response.ok) {
    const error = payload.error ?? { code: "request_failed", message: "Request failed" };
    throw new ApiError(error.code, error.message, error.details ?? {});
  }

  return (payload as ApiEnvelope<T>).data;
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
