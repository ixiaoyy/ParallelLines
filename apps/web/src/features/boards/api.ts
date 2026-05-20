import { apiGet, apiPost } from "@/shared/api/client";

import type { BoardDetailResponse, BoardResponse } from "./model";

export interface CreateBoardRequest {
  slug: string;
  name: string;
  description: string;
  color?: string;
  visibility?: "public" | "private" | "unlisted";
}

export function fetchBoards(): Promise<BoardResponse[]> {
  return apiGet<BoardResponse[]>("/boards");
}

export function fetchBoardDetail(slug: string): Promise<BoardDetailResponse> {
  return apiGet<BoardDetailResponse>(`/boards/${slug}`);
}

export function createBoard(payload: CreateBoardRequest): Promise<BoardResponse> {
  return apiPost<BoardResponse, CreateBoardRequest>("/boards", payload);
}
