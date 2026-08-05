import { useMutation, useQuery } from "@tanstack/vue-query";

import { hasAccessToken } from "@/shared/api/client";
import { queryKeys } from "@/shared/api/queryKeys";

import { fetchPdfTranslationCapabilities, translatePdfToEnglish } from "./api";
import type { PdfTranslationCapabilities, PdfTranslationDownload } from "./model";

/**
 * Owns the authenticated server capability query for the PDF translation workspace.
 * Key parameters: none. Return value: Vue Query capability state.
 * Side effect: fetches once while the user has an access token.
 */
export function usePdfTranslationCapabilities() {
  return useQuery<PdfTranslationCapabilities, Error>({
    queryKey: queryKeys.pdfTranslationCapabilities,
    queryFn: fetchPdfTranslationCapabilities,
    enabled: hasAccessToken(),
    staleTime: 60_000,
  });
}

/**
 * Owns the one-shot PDF upload and binary download mutation.
 * Key parameters: none. Return value: Vue Query mutation accepting a File.
 * Side effect: starts the server translation workflow when mutated.
 */
export function useTranslatePdfToEnglish() {
  return useMutation<PdfTranslationDownload, Error, File>({
    mutationFn: translatePdfToEnglish,
  });
}
