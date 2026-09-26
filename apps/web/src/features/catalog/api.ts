import { apiGet, apiPost } from "@/shared/api/client";

import type {
  CatalogResponse,
  CatalogRatingRequest,
  CatalogRatingResponse,
  CatalogViewResponse,
} from "./model";

export function fetchCatalog(): Promise<CatalogResponse> {
  return apiGet<CatalogResponse>("/catalog");
}

export function rateCatalogProject(
  projectId: string,
  payload: CatalogRatingRequest,
): Promise<CatalogRatingResponse> {
  return apiPost<CatalogRatingResponse, CatalogRatingRequest>(
    `/catalog/projects/${encodeURIComponent(projectId)}/ratings`,
    payload,
  );
}

// 按游戏 ID 记录一次打开并返回累计浏览量；请求最多等待 5 秒，离开页面仍可继续发送。
export async function recordCatalogProjectView(projectId: string): Promise<CatalogViewResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5_000);
  try {
    return await apiPost<CatalogViewResponse, Record<string, never>>(
      `/catalog/projects/${encodeURIComponent(projectId)}/views`,
      {},
      { keepalive: true, signal: controller.signal },
    );
  } finally {
    clearTimeout(timeout);
  }
}
