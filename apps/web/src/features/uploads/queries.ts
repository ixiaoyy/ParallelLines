import { useMutation, useQueryClient } from "@tanstack/vue-query";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import { uploadAvatar, uploadFile } from "./api";
import type { UploadKind, UploadResponse } from "./model";

export function useUploadFile() {
  return useMutation<UploadResponse, Error, { file: File; kind?: UploadKind }>({
    mutationFn: ({ file, kind }) => {
      if (!hasAccessToken()) {
        throw new Error("authentication_required");
      }

      return uploadFile(file, kind ?? "post_attachment");
    },
  });
}

export function useUploadAvatar(username: () => string | undefined) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => {
      if (!hasAccessToken()) {
        throw new Error("authentication_required");
      }

      return uploadAvatar(file);
    },
    onSuccess: (user) => {
      queryClient.setQueryData(queryKeys.currentUser, user);
      const targetUsername = username() ?? user.username;
      void queryClient.invalidateQueries({ queryKey: queryKeys.user(targetUsername) });
    },
  });
}
