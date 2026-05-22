import { apiDelete, apiGet, apiPut } from "@/shared/api/client";
import type { DraftResponse, DraftSaveRequest } from "./model";

export function lookupDraft(targetType: string, targetId = ""): Promise<DraftResponse | null> {
  const params = new URLSearchParams({
    target_type: targetType,
    target_id: targetId,
  });
  return apiGet<DraftResponse | null>(`/drafts/lookup?${params.toString()}`);
}

export function saveDraft(payload: DraftSaveRequest): Promise<DraftResponse> {
  return apiPut<DraftResponse, DraftSaveRequest>("/drafts", payload);
}

export function deleteDraft(targetType: string, targetId = ""): Promise<boolean> {
  const params = new URLSearchParams({
    target_type: targetType,
    target_id: targetId,
  });
  return apiDelete<boolean>(`/drafts?${params.toString()}`);
}
