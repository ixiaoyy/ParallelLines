import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { queryKeys } from "@/shared/api/queryKeys";
import { ApiError } from "@/shared/api/client";

import { fetchCatalog, rateCatalogProject, recordCatalogProjectView } from "./api";
import { toCatalogCategory } from "./model";
import type { CatalogCategory, CatalogRatingResponse, CatalogViewResponse } from "./model";

export function useCatalog() {
  return useQuery<CatalogCategory[], Error>({
    queryKey: queryKeys.catalog,
    queryFn: async () => (await fetchCatalog()).categories.map(toCatalogCategory),
    staleTime: 60_000,
  });
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
    },
    onError: (error, { projectId }) => {
      console.warn("catalog_view_failed", {
        projectId,
        code: error instanceof ApiError ? error.code : error.name,
      });
    },
  });
}
