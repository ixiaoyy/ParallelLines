import { apiGet } from "@/shared/api/client";

import type { BoardDetailResponse, BoardResponse } from "./model";

export function fetchBoards(): Promise<BoardResponse[]> {
  return apiGet<BoardResponse[]>("/boards");
}

export function fetchBoardDetail(slug: string): Promise<BoardDetailResponse> {
  return apiGet<BoardDetailResponse>(`/boards/${slug}`);
}
