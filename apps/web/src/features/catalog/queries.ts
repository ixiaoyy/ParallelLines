import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { queryKeys } from "@/shared/api/queryKeys";

import { fetchCatalog, rateCatalogProject } from "./api";
import { toCatalogCategory } from "./model";
import type { CatalogCategory, CatalogRatingResponse } from "./model";

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
                  myScore: result.my_score,
                }
              : project,
          ),
        })),
      );
    },
  });
}
