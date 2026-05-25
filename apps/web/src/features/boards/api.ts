import { apiDelete, apiGet, apiPost, apiPut } from "@/shared/api/client";

import type {
  BoardDetailResponse,
  BoardMemberRemoveResponse,
  BoardMemberResponse,
  BoardMemberUpdateRequest,
  BoardResponse,
  BoardSettingsResponse,
  BoardSettingsUpdateRequest,
} from "./model";

export interface CreateBoardRequest {
  slug: string;
  name: string;
  description: string;
  color?: string;
  visibility?: "public" | "private" | "unlisted";
  parent_board_id?: string | null;
  parent_board_slug?: string | null;
  required_tags?: string[];
  allowed_tags?: string[];
  post_template?: string | null;
  default_notification_level?: "muted" | "normal" | "tracking" | "watching";
  default_sort?: "latest" | "hot" | "top";
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

export function fetchBoardSettings(slug: string): Promise<BoardSettingsResponse> {
  return apiGet<BoardSettingsResponse>(`/boards/${encodeURIComponent(slug)}/settings`);
}

export function updateBoardSettings(
  slug: string,
  payload: BoardSettingsUpdateRequest,
): Promise<BoardResponse> {
  return apiPut<BoardResponse, BoardSettingsUpdateRequest>(
    `/boards/${encodeURIComponent(slug)}/settings`,
    payload,
  );
}

export function updateBoardMember(
  slug: string,
  username: string,
  payload: BoardMemberUpdateRequest,
): Promise<BoardMemberResponse> {
  return apiPut<BoardMemberResponse, BoardMemberUpdateRequest>(
    `/boards/${encodeURIComponent(slug)}/members/${encodeURIComponent(username)}`,
    payload,
  );
}

export function removeBoardMember(
  slug: string,
  username: string,
): Promise<BoardMemberRemoveResponse> {
  return apiDelete<BoardMemberRemoveResponse>(
    `/boards/${encodeURIComponent(slug)}/members/${encodeURIComponent(username)}`,
  );
}
