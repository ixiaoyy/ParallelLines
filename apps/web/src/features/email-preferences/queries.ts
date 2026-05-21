import { useMutation, useQuery, useQueryClient } from "@tanstack/vue-query";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import { fetchEmailPreferences, updateEmailPreferences } from "./api";
import type { EmailPreferenceResponse, EmailPreferenceUpdateRequest } from "./model";

export function useEmailPreferences() {
  return useQuery<EmailPreferenceResponse | null, Error>({
    queryKey: queryKeys.emailPreferences,
    queryFn: async () => {
      if (!hasAccessToken()) {
        return null;
      }

      return fetchEmailPreferences();
    },
    retry: false,
    staleTime: 60_000,
  });
}

export function useUpdateEmailPreferences() {
  const queryClient = useQueryClient();

  return useMutation<EmailPreferenceResponse, Error, EmailPreferenceUpdateRequest>({
    mutationFn: updateEmailPreferences,
    onSuccess: (preferences) => {
      queryClient.setQueryData(queryKeys.emailPreferences, preferences);
    },
  });
}
