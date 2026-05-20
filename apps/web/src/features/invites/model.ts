import type { BoardResponse } from "@/features/boards/model";

export interface BoardInviteResponse {
  id: string;
  board_id: string;
  board_slug: string;
  board_name: string;
  board_description: string;
  board_color: string;
  inviter_id: string;
  inviter_name: string;
  invitee_id: string;
  invitee_name: string;
  status: "pending" | "accepted" | "declined" | "revoked" | "expired";
  expires_at: string | null;
  responded_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MyBoardInvitesResponse {
  received: BoardInviteResponse[];
  managed: BoardInviteResponse[];
  owned_boards: BoardResponse[];
}

export interface CreateBoardInviteRequest {
  board_id: string;
  username: string;
}

export interface BoardInviteVM {
  id: string;
  boardId: string;
  boardSlug: string;
  boardName: string;
  boardDescription: string;
  boardColor: string;
  inviterName: string;
  inviteeName: string;
  status: BoardInviteResponse["status"];
  createdAt: string;
}

export interface MyBoardInvitesVM {
  received: BoardInviteVM[];
  managed: BoardInviteVM[];
  ownedBoards: BoardResponse[];
}

export function toBoardInvite(invite: BoardInviteResponse): BoardInviteVM {
  return {
    id: invite.id,
    boardId: invite.board_id,
    boardSlug: invite.board_slug,
    boardName: invite.board_name,
    boardDescription: invite.board_description,
    boardColor: invite.board_color,
    inviterName: invite.inviter_name,
    inviteeName: invite.invitee_name,
    status: invite.status,
    createdAt: invite.created_at,
  };
}

export function toMyBoardInvites(response: MyBoardInvitesResponse): MyBoardInvitesVM {
  return {
    received: response.received.map(toBoardInvite),
    managed: response.managed.map(toBoardInvite),
    ownedBoards: response.owned_boards,
  };
}
