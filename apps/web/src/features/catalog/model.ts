import { resolveApiAssetUrl } from "@/shared/api/client";

export type CatalogJsonValue = string | number | boolean | null
  | CatalogJsonValue[] | { [key: string]: CatalogJsonValue };
export type CatalogAiSourceKind = "independent_ai" | "user_accepted_external_ai";

export interface CatalogAiRatingResponse {
  score: number | null;
  label: "AI评分";
  assessment_id: string;
  rule_version: string;
  weight_version: string;
  source_kind: CatalogAiSourceKind;
  evaluated_at: string | null;
  reported_review_date: string | null;
  reported_timezone: string | null;
  game_version: string | null;
  dimensions: Array<{ key: string; label: string; score: number | null; weight: number }>;
  play_scope: Record<string, CatalogJsonValue>;
  limitations: string[];
}

export interface CatalogAiRating {
  score: number | null;
  label: "AI评分";
  assessmentId: string;
  ruleVersion: string;
  weightVersion: string;
  sourceKind: CatalogAiSourceKind;
  evaluatedAt: string | null;
  reportedReviewDate: string | null;
  reportedTimezone: string | null;
  gameVersion: string | null;
  dimensions: Array<{ key: string; label: string; score: number | null; weight: number }>;
  playScope: Record<string, CatalogJsonValue>;
  limitations: string[];
}

export interface CatalogProjectResponse {
  id: string;
  slug: string;
  name: string;
  url: string;
  kind: "external" | "internal";
  description: string | null;
  author_name: string | null;
  author_url: string | null;
  icon_url: string | null;
  created_at: string;
  average_score: number | null;
  rating_count: number;
  rating_score_sum: number;
  view_count: number;
  my_score: number | null;
  ai_rating?: CatalogAiRatingResponse | null;
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
  rating_score_sum: number;
  my_score: number;
}

export interface CatalogViewResponse {
  project_id: string;
  view_count: number;
}

export interface CatalogProject {
  id: string;
  slug: string;
  name: string;
  url: string;
  kind: "external" | "internal";
  description: string | null;
  authorName: string | null;
  authorUrl?: string;
  iconUrl?: string;
  createdAt: string;
  averageScore: number | null;
  ratingCount: number;
  ratingScoreSum: number;
  viewCount: number;
  myScore: number | null;
  host: string;
  aiRating?: CatalogAiRating | null;
}

export interface CatalogCategory {
  id: string;
  slug: string;
  name: string;
  iconUrl?: string;
  projects: CatalogProject[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isJsonValue(value: unknown): value is CatalogJsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (Array.isArray(value)) return value.every(isJsonValue);
  return isJsonObject(value);
}

function isJsonObject(value: unknown): value is Record<string, CatalogJsonValue> {
  return isRecord(value) && Object.values(value).every(isJsonValue);
}

function isScore(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 10);
}

function isAiDimension(value: unknown): value is CatalogAiRatingResponse["dimensions"][number] {
  return isRecord(value) && typeof value.key === "string" && typeof value.label === "string"
    && isScore(value.score) && typeof value.weight === "number" && Number.isFinite(value.weight)
    && value.weight >= 0 && value.weight <= 1;
}

/** Keep incomplete scores and unknown version/date data null; never invent an AI rating. */
export function toCatalogAiRating(value: unknown): CatalogAiRating | null {
  if (!isRecord(value) || value.label !== "AI评分" || !isScore(value.score)
    || typeof value.assessment_id !== "string" || !value.assessment_id
    || typeof value.rule_version !== "string" || !value.rule_version
    || typeof value.weight_version !== "string" || !value.weight_version
    || (value.source_kind !== "independent_ai" && value.source_kind !== "user_accepted_external_ai")
    || (value.evaluated_at !== null && (typeof value.evaluated_at !== "string" || !Number.isFinite(Date.parse(value.evaluated_at))))
    || (value.reported_review_date !== null && typeof value.reported_review_date !== "string")
    || (value.reported_timezone !== null && typeof value.reported_timezone !== "string")
    || (value.game_version !== null && typeof value.game_version !== "string")
    || !Array.isArray(value.dimensions) || !value.dimensions.every(isAiDimension)
    || !isJsonObject(value.play_scope)
    || !Array.isArray(value.limitations) || !value.limitations.every((item): item is string => typeof item === "string")) {
    return null;
  }
  return {
    score: value.score,
    label: value.label,
    assessmentId: value.assessment_id,
    ruleVersion: value.rule_version,
    weightVersion: value.weight_version,
    sourceKind: value.source_kind,
    evaluatedAt: value.evaluated_at,
    reportedReviewDate: value.reported_review_date,
    reportedTimezone: value.reported_timezone,
    gameVersion: value.game_version,
    dimensions: value.dimensions.map((dimension) => ({ ...dimension })),
    playScope: value.play_scope,
    limitations: [...value.limitations],
  };
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

// 作者链接只允许 HTTPS，避免后台数据异常时把不安全地址放入公开卡片。
function catalogAuthorUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:" || !parsed.hostname || parsed.username || parsed.password) {
      return undefined;
    }
    return parsed.toString();
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
        authorUrl: catalogAuthorUrl(project.author_url),
        iconUrl: catalogIconUrl(project.icon_url),
        createdAt: project.created_at,
        averageScore: project.average_score,
        ratingCount: project.rating_count,
        ratingScoreSum: project.rating_score_sum ?? 0,
        // 旧版目录响应尚无浏览量时从零展示，不推算历史访问。
        viewCount: project.view_count ?? 0,
        myScore: project.my_score,
        aiRating: toCatalogAiRating(project.ai_rating),
        host,
      };
    }),
  };
}
