import { apiBlob, apiGet, apiPost, apiRequest } from "@/shared/api/client";

import type {
  AdminCatalogSubmission,
  AdminCatalogSubmissions,
  CatalogSubmissionCreateResult,
  CatalogSubmissionPayload,
} from "./submissionsModel";

// 游客仅提交待审记录；公开目录在管理员批准前不会显示该项目。
export function submitCatalogProject(
  payload: CatalogSubmissionPayload,
): Promise<CatalogSubmissionCreateResult> {
  const body = new FormData();
  body.append("category_name", payload.category_name);
  body.append("project_name", payload.project_name);
  body.append("url", payload.url);
  if (payload.author_name) body.append("author_name", payload.author_name);
  if (payload.contact) body.append("contact", payload.contact);
  if (payload.cover) body.append("cover", payload.cover);
  return apiRequest<CatalogSubmissionCreateResult>("/catalog/submissions", {
    method: "POST",
    body,
  });
}

// 读取后台投稿列表，联系方式仅由已登录管理员接口返回。
export function fetchAdminCatalogSubmissions(): Promise<AdminCatalogSubmissions> {
  return apiGet<AdminCatalogSubmissions>("/admin/catalog/submissions");
}

// 审核通过或拒绝指定投稿；服务端负责状态与目录写入的事务边界。
export function reviewCatalogSubmission(
  submissionId: string,
  decision: "approve" | "reject",
): Promise<AdminCatalogSubmission> {
  return apiPost<AdminCatalogSubmission, { decision: "approve" | "reject" }>(
    `/admin/catalog/submissions/${encodeURIComponent(submissionId)}/review`,
    { decision },
  );
}

// 封面预览需要管理员凭据，不能直接把受保护地址放进 img 标签。
export async function fetchAdminSubmissionCover(submissionId: string): Promise<Blob> {
  const { blob } = await apiBlob(`/admin/catalog/submissions/${encodeURIComponent(submissionId)}/cover`);
  return blob;
}
