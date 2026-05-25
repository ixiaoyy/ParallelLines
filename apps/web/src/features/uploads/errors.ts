import { ApiError } from "@/shared/api/client";

export function uploadErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "upload_too_large") {
      return "文件超过当前上传大小限制。";
    }
    if (error.code === "upload_type_not_allowed" || error.code === "upload_mime_mismatch") {
      return "文件类型不被允许，或内容与扩展名不一致。";
    }
  }

  return "上传失败：请确认已登录且文件类型安全。";
}
