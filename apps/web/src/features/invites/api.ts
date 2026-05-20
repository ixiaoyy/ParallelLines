import { apiGet, apiPost, apiPut } from "@/shared/api/client";

import type {
  BoardInviteResponse,
  CreateBoardInviteRequest,
  MyBoardInvitesResponse,
} from "./model";

export function fetchMyBoardInvites(): Promise<MyBoardInvitesResponse> {
  return apiGet<MyBoardInvitesResponse>("/invites");
}

export function createBoardInvite(payload: CreateBoardInviteRequest): Promise<BoardInviteResponse> {
  return apiPost<BoardInviteResponse, CreateBoardInviteRequest>("/invites", payload);
}

export function acceptBoardInvite(inviteId: string): Promise<BoardInviteResponse> {
  return apiPut<BoardInviteResponse, Record<string, never>>(`/invites/${inviteId}/accept`);
}

export function declineBoardInvite(inviteId: string): Promise<BoardInviteResponse> {
  return apiPut<BoardInviteResponse, Record<string, never>>(`/invites/${inviteId}/decline`);
}

export function revokeBoardInvite(inviteId: string): Promise<BoardInviteResponse> {
  return apiPut<BoardInviteResponse, Record<string, never>>(`/invites/${inviteId}/revoke`);
}
