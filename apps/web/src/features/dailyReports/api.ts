import { apiDelete, apiGet, apiPost, apiPut } from "@/shared/api/client";

import type {
  DailyReportConfirmRequest,
  DailyReportFollowupRequest,
  DailyReportInput,
  DailyReportPreferenceAcceptRequest,
  DailyReportProfile,
  DailyReportProfileUpdateRequest,
  DailyReportRecord,
  DailyReportSession,
} from "./model";

export function fetchDailyReportProfile(): Promise<DailyReportProfile> {
  return apiGet<DailyReportProfile>("/daily-reports/profile");
}

export function updateDailyReportProfile(
  payload: DailyReportProfileUpdateRequest,
): Promise<DailyReportProfile> {
  return apiPut<DailyReportProfile, DailyReportProfileUpdateRequest>(
    "/daily-reports/profile",
    payload,
  );
}

export function resetDailyReportProfile(): Promise<DailyReportProfile> {
  return apiPost<DailyReportProfile, Record<string, never>>(
    "/daily-reports/profile/reset",
    {},
  );
}

export function acceptDailyReportPreference(
  payload: DailyReportPreferenceAcceptRequest,
): Promise<DailyReportProfile> {
  return apiPost<DailyReportProfile, DailyReportPreferenceAcceptRequest>(
    "/daily-reports/profile/preferences",
    payload,
  );
}

export function startDailyReportSession(payload: DailyReportInput): Promise<DailyReportSession> {
  return apiPost<DailyReportSession, DailyReportInput>("/daily-reports/sessions", payload);
}

export function fetchDailyReportSession(sessionId: string): Promise<DailyReportSession> {
  return apiGet<DailyReportSession>(
    `/daily-reports/sessions/${encodeURIComponent(sessionId)}`,
  );
}

export function continueDailyReportSession(
  sessionId: string,
  payload: DailyReportFollowupRequest,
): Promise<DailyReportSession> {
  return apiPost<DailyReportSession, DailyReportFollowupRequest>(
    `/daily-reports/sessions/${encodeURIComponent(sessionId)}/messages`,
    payload,
  );
}

export function confirmDailyReportSession(
  sessionId: string,
  payload: DailyReportConfirmRequest,
): Promise<DailyReportRecord> {
  return apiPost<DailyReportRecord, DailyReportConfirmRequest>(
    `/daily-reports/sessions/${encodeURIComponent(sessionId)}/confirm`,
    payload,
  );
}

export function fetchDailyReports(limit = 30): Promise<DailyReportRecord[]> {
  return apiGet<DailyReportRecord[]>(`/daily-reports?limit=${limit}`);
}

export function deleteDailyReport(reportId: string): Promise<boolean> {
  return apiDelete<boolean>(`/daily-reports/${encodeURIComponent(reportId)}`);
}

export function clearDailyReportHistory(): Promise<boolean> {
  return apiDelete<boolean>("/daily-reports/history");
}
