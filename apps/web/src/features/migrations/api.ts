import { apiGet, apiPost } from "@/shared/api/client";

import type {
  MigrationExportResponse,
  MigrationImportRequest,
  MigrationImportResponse,
} from "./model";

export function previewMigrationImport(
  payload: MigrationImportRequest,
): Promise<MigrationImportResponse> {
  return apiPost<MigrationImportResponse, MigrationImportRequest>(
    "/admin/migrations/import/preview",
    payload,
  );
}

export function runMigrationImport(payload: MigrationImportRequest): Promise<MigrationImportResponse> {
  return apiPost<MigrationImportResponse, MigrationImportRequest>(
    "/admin/migrations/import/run",
    payload,
  );
}

export function fetchMigrationExport(): Promise<MigrationExportResponse> {
  return apiGet<MigrationExportResponse>("/admin/migrations/export");
}
