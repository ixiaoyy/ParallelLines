import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData, type QueryClient } from "@tanstack/vue-query";
import { computed, toValue, type MaybeRefOrGetter } from "vue";

import { queryKeys } from "@/shared/api/queryKeys";
import { ApiError } from "@/shared/api/client";

import { fetchCatalog, fetchCatalogOverview, fetchCatalogCategoryPage, rateCatalogProject, recordCatalogProjectView } from "./api";
import { toCatalogCategory, toCatalogBrowseProject } from "./model";
import type { CatalogBrowseProject, CatalogCategory, CatalogCategoryPage, CatalogOverview, CatalogRatingResponse, CatalogViewResponse } from "./model";

export function useCatalog(enabled: MaybeRefOrGetter<boolean> = true) {
  return useQuery<CatalogCategory[], Error>({
    queryKey: queryKeys.catalog,
    queryFn: async ({ signal }) => (await fetchCatalog(signal)).categories.map(toCatalogCategory),
    enabled: computed(() => toValue(enabled)),
    staleTime: 60_000,
  });
}

/** 缓存公开概览 60 秒；切换专题时只保留分类元数据，不显示上一专题的精选。 */
export function useCatalogOverview(slugs: MaybeRefOrGetter<readonly string[] | undefined>, offset: MaybeRefOrGetter<number>, enabled: MaybeRefOrGetter<boolean>) {
  return useQuery<CatalogOverview, Error>({
    queryKey: computed(() => queryKeys.catalogOverview(toValue(slugs)?.join(",") ?? null, toValue(offset))),
    queryFn: async ({ signal }) => {
      const data = await fetchCatalogOverview(toValue(slugs), toValue(offset), signal);
      return {
        categories: data.categories.map((category) => ({ ...toCatalogCategory({ ...category, projects: [] }), total: category.total })),
        hero: { projects: data.hero.projects.map(toCatalogBrowseProject), total: data.hero.total, nextOffset: data.hero.next_offset },
      };
    },
    enabled: computed(() => toValue(enabled)), staleTime: 60_000, gcTime: 10 * 60_000, retry: false,
    placeholderData: (previous) => previous ? { categories: previous.categories, hero: { projects: [], total: 0, nextOffset: null } } : undefined,
  });
}

/** 分类页按游标缓存，不把屏宽和本次 limit 加入键，缩放或返回页面可复用已有前缀。 */
export function useCatalogCategoryPages(slug: MaybeRefOrGetter<string>, priority: readonly string[], limit: MaybeRefOrGetter<number>) {
  return useInfiniteQuery({
    queryKey: computed(() => queryKeys.catalogCategory(toValue(slug), priority.join(","))),
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam, signal }): Promise<CatalogCategoryPage> => {
      const data = await fetchCatalogCategoryPage(toValue(slug), toValue(limit), pageParam, priority, signal);
      if (data.has_more && (!data.next_cursor || data.next_cursor === pageParam || !data.projects.length)) {
        throw new Error("分类分页未推进，请重试。");
      }
      return { projects: data.projects.map(toCatalogBrowseProject), total: data.total, nextCursor: data.next_cursor, hasMore: data.has_more };
    },
    getNextPageParam: (page) => page.hasMore ? page.nextCursor : undefined,
    enabled: false, staleTime: 60_000, gcTime: 10 * 60_000, retry: false,
  });
}

/** 同步重复出现的公开卡片；只写公共统计，当前用户评分仍留在原私有目录缓存。 */
function updatePublicProjects(client: QueryClient, update: (project: CatalogBrowseProject) => CatalogBrowseProject): void {
  client.setQueriesData<CatalogOverview>({ queryKey: queryKeys.catalogOverviewRoot }, (data) => data
    ? { ...data, hero: { ...data.hero, projects: data.hero.projects.map(update) } } : data);
  client.setQueriesData<InfiniteData<CatalogCategoryPage>>({ queryKey: queryKeys.catalogCategoryRoot }, (data) => data
    ? { ...data, pages: data.pages.map((page) => ({ ...page, projects: page.projects.map(update) })) } : data);
}

export function useRateCatalogProject() {
  const queryClient = useQueryClient();

  return useMutation<CatalogRatingResponse, Error, { projectId: string; score: number }>({
    mutationFn: ({ projectId, score }) => rateCatalogProject(projectId, { score }),
    onSuccess: (result) => {
      // 评分不可修改；重复请求返回首次评分，直接用服务端结果更新目录卡片。
      queryClient.setQueryData<CatalogCategory[]>(queryKeys.catalog, (categories) =>
        categories?.map((category) => ({
          ...category,
          projects: category.projects.map((project) =>
            project.id === result.project_id
              ? {
                  ...project,
                  averageScore: result.average_score,
                  ratingCount: result.rating_count,
                  ratingScoreSum: result.rating_score_sum ?? project.ratingScoreSum,
                  myScore: result.my_score,
                }
              : project,
          ),
        })),
      );
      updatePublicProjects(queryClient, (project) => project.id === result.project_id ? {
        ...project, averageScore: result.average_score, ratingCount: result.rating_count,
        ratingScoreSum: result.rating_score_sum ?? project.ratingScoreSum, myScore: null,
      } : project);
    },
  });
}

// 记录真实打开；失败不补加浏览量、不重试，也不阻塞浏览器打开游戏。
export function useRecordCatalogProjectView() {
  const queryClient = useQueryClient();

  return useMutation<CatalogViewResponse, Error, { projectId: string }>({
    mutationFn: ({ projectId }) => recordCatalogProjectView(projectId),
    retry: false,
    onSuccess: (result) => {
      // 同一游戏可被连续打开，响应倒序到达时保留较大的服务端累计值。
      queryClient.setQueryData<CatalogCategory[]>(queryKeys.catalog, (categories) =>
        categories?.map((category) => ({
          ...category,
          projects: category.projects.map((project) =>
            project.id === result.project_id
              ? { ...project, viewCount: Math.max(project.viewCount ?? 0, result.view_count) }
              : project,
          ),
        })),
      );
      updatePublicProjects(queryClient, (project) => project.id === result.project_id
        ? { ...project, viewCount: Math.max(project.viewCount ?? 0, result.view_count) } : project);
    },
    onError: (error, { projectId }) => {
      console.warn("catalog_view_failed", {
        projectId,
        code: error instanceof ApiError ? error.code : error.name,
      });
    },
  });
}
