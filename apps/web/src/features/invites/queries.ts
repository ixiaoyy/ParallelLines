import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import {
  acceptBoardInvite,
  createBoardInvite,
  declineBoardInvite,
  fetchMyBoardInvites,
  revokeBoardInvite,
} from "./api";
import { toBoardInvite, toMyBoardInvites } from "./model";
import type { BoardInviteVM, CreateBoardInviteRequest, MyBoardInvitesVM } from "./model";

export function useMyBoardInvites() {
  return useQuery<MyBoardInvitesVM>({
    queryKey: queryKeys.invites,
    queryFn: async () => toMyBoardInvites(await fetchMyBoardInvites()),
    enabled: hasAccessToken(),
    staleTime: 20_000,
  });
}

export function useCreateBoardInvite() {
  const queryClient = useQueryClient();

  return useMutation<BoardInviteVM, Error, CreateBoardInviteRequest>({
    mutationFn: async (payload) => {
      if (!hasAccessToken()) {
        throw new Error("authentication_required");
      }
      return toBoardInvite(await createBoardInvite(payload));
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.invites });
    },
  });
}

export function useInviteAction() {
  const queryClient = useQueryClient();

  return useMutation<
    BoardInviteVM,
    Error,
    { inviteId: string; action: "accept" | "decline" | "revoke" }
  >({
    mutationFn: async ({ inviteId, action }) => {
      if (!hasAccessToken()) {
        throw new Error("authentication_required");
      }
      if (action === "accept") {
        return toBoardInvite(await acceptBoardInvite(inviteId));
      }
      if (action === "decline") {
        return toBoardInvite(await declineBoardInvite(inviteId));
      }
      return toBoardInvite(await revokeBoardInvite(inviteId));
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.invites });
      void queryClient.invalidateQueries({ queryKey: queryKeys.boards });
    },
  });
}
