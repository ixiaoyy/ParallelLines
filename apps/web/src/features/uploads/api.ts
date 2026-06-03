import { apiRequest } from "@/shared/api/client";

import type { UserPublic } from "@/features/auth/model";
import { preparePostAttachmentFile } from "./imageCompression";
import type { UploadKind, UploadResponse } from "./model";

/**
 * Uploads a composer attachment through the shared API client.
 * Key parameters: `file` is the selected browser file and `kind` controls backend upload usage. Return value: upload metadata.
 * Side effect: may downscale large post images before sending multipart data to the backend.
 */
export async function uploadFile(file: File, kind: UploadKind = "post_attachment"): Promise<UploadResponse> {
  const uploadFile = kind === "post_attachment" ? await preparePostAttachmentFile(file) : file;
  const formData = new FormData();
  formData.append("file", uploadFile);
  formData.append("kind", kind);
  return apiRequest<UploadResponse>("/uploads", {
    method: "POST",
    body: formData,
  });
}

/**
 * Uploads an avatar image through the shared API client.
 * Key parameter: `file` is the selected browser file. Return value: refreshed public user data.
 * Side effect: sends multipart data to the backend without post-attachment compression.
 */
export function uploadAvatar(file: File): Promise<UserPublic> {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<UserPublic>("/uploads/avatar", {
    method: "POST",
    body: formData,
  });
}
