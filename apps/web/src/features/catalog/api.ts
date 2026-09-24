import { apiGet, apiPost } from "@/shared/api/client";

import type {
  CatalogResponse,
  CatalogRatingRequest,
  CatalogRatingResponse,
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
