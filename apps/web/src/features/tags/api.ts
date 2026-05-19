import { apiGet } from "@/shared/api/client";

import type { TagResponse } from "./model";

export function fetchTags(limit = 30): Promise<TagResponse[]> {
  return apiGet<TagResponse[]>(`/tags?limit=${limit}`);
}
