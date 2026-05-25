import { apiGet, apiPost, apiPut } from "@/shared/api/client";

import type {
  ExternalIntegrationEventInfo,
  ExternalIntegrationInfo,
  ExternalIntegrationUpdateRequest,
  GitHubIssuePreview,
} from "./model";

export function fetchExternalIntegrations(): Promise<ExternalIntegrationInfo[]> {
  return apiGet<ExternalIntegrationInfo[]>("/admin/external-integrations");
}

export function updateExternalIntegration(
  provider: string,
  payload: ExternalIntegrationUpdateRequest,
): Promise<ExternalIntegrationInfo> {
  return apiPut<ExternalIntegrationInfo, ExternalIntegrationUpdateRequest>(
    `/admin/external-integrations/${encodeURIComponent(provider)}`,
    payload,
  );
}

export function fetchExternalIntegrationEvents(): Promise<ExternalIntegrationEventInfo[]> {
  return apiGet<ExternalIntegrationEventInfo[]>("/admin/external-integrations/events?limit=20");
}

export function retryExternalIntegrationEvent(eventId: string): Promise<ExternalIntegrationEventInfo> {
  return apiPost<ExternalIntegrationEventInfo, Record<string, never>>(
    `/admin/external-integrations/events/${eventId}/retry`,
    {},
  );
}

export function fetchGitHubIssuePreview(url: string): Promise<GitHubIssuePreview> {
  return apiGet<GitHubIssuePreview>(`/integrations/github/issue?url=${encodeURIComponent(url)}`);
}
