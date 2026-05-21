import { apiGet, apiPut } from "@/shared/api/client";

import type { EmailPreferenceResponse, EmailPreferenceUpdateRequest } from "./model";

export function fetchEmailPreferences(): Promise<EmailPreferenceResponse> {
  return apiGet<EmailPreferenceResponse>("/email/preferences");
}

export function updateEmailPreferences(
  payload: EmailPreferenceUpdateRequest,
): Promise<EmailPreferenceResponse> {
  return apiPut<EmailPreferenceResponse, EmailPreferenceUpdateRequest>(
    "/email/preferences",
    payload,
  );
}
