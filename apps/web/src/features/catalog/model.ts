import { resolveApiAssetUrl } from "@/shared/api/client";

export interface CatalogProjectResponse {
  id: string;
  slug: string;
  name: string;
  url: string;
  kind: "external" | "internal";
  description: string | null;
  author_name?: string | null;
  icon_url: string | null;
  created_at: string;
  average_score: number | null;
  rating_count: number;
  my_score: number | null;
}

export interface CatalogCategoryResponse {
  id: string;
  slug: string;
  name: string;
  icon_url: string | null;
  projects: CatalogProjectResponse[];
}

export interface CatalogResponse {
  categories: CatalogCategoryResponse[];
}

export interface CatalogRatingRequest {
  score: number;
}

export interface CatalogRatingResponse {
  project_id: string;
  average_score: number | null;
  rating_count: number;
  my_score: number;
}

export interface CatalogProject {
  id: string;
  slug: string;
  name: string;
  url: string;
  kind: "external" | "internal";
  description: string | null;
  authorName: string | null;
  iconUrl?: string;
  createdAt: string;
  averageScore: number | null;
  ratingCount: number;
  myScore: number | null;
  host: string;
}

export interface CatalogCategory {
  id: string;
  slug: string;
  name: string;
  iconUrl?: string;
  projects: CatalogProject[];
}

// 校验后台图标地址，只返回本站上传资源的可显示 URL，避免第三方图片热链。
// 参数为可空的 API 图标地址；非上传资源返回 undefined，不影响文字图标兜底。
function catalogIconUrl(url: string | null): string | undefined {
  if (!url) return undefined;
  try {
    const parsed = new URL(url, "https://catalog.invalid");
    if (!/^\/(?:api\/v1\/)?uploads\/[^/]+\/(?:content|thumbnail)$/.test(parsed.pathname)) {
      return undefined;
    }
    return resolveApiAssetUrl(url);
  } catch {
    return undefined;
  }
}

// 将一个 API 分类及其项目映射为页面结构；外链显示域名，站内项目不显示域名。
// 参数是 API 分类，返回可直接用于筛选和展示的分类，不产生写入。
export function toCatalogCategory(category: CatalogCategoryResponse): CatalogCategory {
  return {
    id: category.id,
    slug: category.slug,
    name: category.name,
    iconUrl: catalogIconUrl(category.icon_url),
    projects: category.projects.map((project) => {
      let host = "";
      if (project.kind === "external") {
        try {
          host = new URL(project.url).hostname.replace(/^www\./, "");
        } catch {
          host = "";
        }
      }
      return {
        id: project.id,
        slug: project.slug,
        name: project.name,
        url: project.url,
        kind: project.kind,
        description: project.description,
        authorName: project.author_name ?? null,
        iconUrl: catalogIconUrl(project.icon_url),
        createdAt: project.created_at,
        averageScore: project.average_score,
        ratingCount: project.rating_count,
        myScore: project.my_score,
        host,
      };
    }),
  };
}
