import { apiGet, apiPost, apiPut } from "@/shared/api/client";

import type {
  AdminCatalog,
  AdminCatalogCategory,
  AdminCatalogProject,
  CategoryDraftPayload,
  ProjectDraftPayload,
} from "./adminModel";

// 读取后台完整目录，包含已隐藏的分类和项目，供管理页继续编辑。
export function fetchAdminCatalog(): Promise<AdminCatalog> {
  return apiGet<AdminCatalog>("/admin/catalog");
}

// 新增分类；固定标识在创建后由管理页保持只读，避免链接和关联数据漂移。
export function createCatalogCategory(payload: CategoryDraftPayload): Promise<AdminCatalogCategory> {
  return apiPost<AdminCatalogCategory, CategoryDraftPayload>("/admin/catalog/categories", payload);
}

// 更新分类的名称、排序、图标或显示状态，不删除现有项目。
export function updateCatalogCategory(
  categoryId: string,
  payload: CategoryDraftPayload,
): Promise<AdminCatalogCategory> {
  return apiPut<AdminCatalogCategory, CategoryDraftPayload>(
    `/admin/catalog/categories/${encodeURIComponent(categoryId)}`,
    payload,
  );
}

// 新增外部项目；站内项目由现有迁移配置，不从后台创建任意站内地址。
export function createCatalogProject(payload: ProjectDraftPayload): Promise<AdminCatalogProject> {
  return apiPost<AdminCatalogProject, ProjectDraftPayload>("/admin/catalog/projects", payload);
}

// 更新项目元数据；调用方应保留站内项目的固定地址与类型。
export function updateCatalogProject(
  projectId: string,
  payload: ProjectDraftPayload,
): Promise<AdminCatalogProject> {
  return apiPut<AdminCatalogProject, ProjectDraftPayload>(
    `/admin/catalog/projects/${encodeURIComponent(projectId)}`,
    payload,
  );
}
