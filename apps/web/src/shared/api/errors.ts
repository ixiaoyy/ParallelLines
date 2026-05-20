import { ApiError } from "./client";

export function isApiErrorCode(error: unknown, code: string): error is ApiError {
  return error instanceof ApiError && error.code === code;
}

export function contentPolicyMessage(error: unknown, fallback: string): string {
  if (isApiErrorCode(error, "content_policy_violation")) {
    return "内容命中社区安全规则，请修改后再发布。";
  }

  return fallback;
}
