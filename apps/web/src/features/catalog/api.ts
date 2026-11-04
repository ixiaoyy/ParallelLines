import { apiGet, apiPost, publicApiGet } from "@/shared/api/client";

import type {
  CatalogResponse,
  CatalogRatingRequest,
  CatalogRatingResponse,
  CatalogViewResponse,
  CatalogOverviewResponse,
  CatalogCategoryPageResponse,
} from "./model";

export function fetchCatalog(signal?: AbortSignal): Promise<CatalogResponse> {
  return apiGet<CatalogResponse>("/catalog", { signal });
}

/** 读取公开分类概览和六项精选；undefined 为全部，空候选明确请求空专题。 */
export function fetchCatalogOverview(slugs: readonly string[] | undefined, offset: number, signal?: AbortSignal): Promise<CatalogOverviewResponse> {
  const query = new URLSearchParams({ hero_offset: String(offset) });
  if (slugs !== undefined) query.set("hero_slugs", slugs.join(","));
  return publicApiGet<CatalogOverviewResponse>(`/catalog/overview?${query}`, signal);
}

/** 按服务端游标读取一批真实分类项目；请求量来自横排几何，不回退到全量目录。 */
export function fetchCatalogCategoryPage(slug: string, limit: number, cursor: string | null, prioritySlugs: readonly string[], signal?: AbortSignal): Promise<CatalogCategoryPageResponse> {
  const query = new URLSearchParams({ limit: String(limit), priority_slugs: prioritySlugs.join(",") });
  if (cursor) query.set("cursor", cursor);
  return publicApiGet<CatalogCategoryPageResponse>(`/catalog/categories/${encodeURIComponent(slug)}/projects?${query}`, signal);
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
