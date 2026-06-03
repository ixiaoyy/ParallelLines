import { ApiError } from "./client";

export function isApiErrorCode(error: unknown, code: string): error is ApiError {
  return error instanceof ApiError && error.code === code;
}

export function contentPolicyMessage(error: unknown, fallback: string): string {
  if (isApiErrorCode(error, "content_policy_violation")) {
    return "内容命中社区安全规则，请修改后再发布。";
  }

  if (isApiErrorCode(error, "content_pending_review")) {
    return "内容已提交审核，暂未公开发布；你可以在“我的内容复核”查看进度。";
  }

  return fallback;
}
