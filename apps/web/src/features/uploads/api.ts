import { apiRequest } from "@/shared/api/client";

import type { UserPublic } from "@/features/auth/model";
import type { UploadKind, UploadResponse } from "./model";

export function uploadFile(file: File, kind: UploadKind = "post_attachment"): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("kind", kind);
  return apiRequest<UploadResponse>("/uploads", {
    method: "POST",
    body: formData,
  });
}

export function uploadAvatar(file: File): Promise<UserPublic> {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<UserPublic>("/uploads/avatar", {
    method: "POST",
    body: formData,
  });
}
