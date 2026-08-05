import { apiBlob, apiGet } from "@/shared/api/client";

import type { PdfTranslationCapabilities, PdfTranslationDownload } from "./model";

/**
 * Loads server-owned PDF limits and provider availability for the current user.
 * Key parameters: none. Return value: safe translation capabilities with no credentials.
 * Side effect: performs one authenticated API request.
 */
export function fetchPdfTranslationCapabilities(): Promise<PdfTranslationCapabilities> {
  return apiGet<PdfTranslationCapabilities>("/pdf-translations/capabilities");
}

/**
 * Uploads one PDF and returns the verified English-only binary response.
 * Key parameter: `file` is the browser-selected PDF. Return value: Blob plus safe download metadata.
 * Side effect: may refresh authentication and invokes the server translation workflow.
 */
export async function translatePdfToEnglish(file: File): Promise<PdfTranslationDownload> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiBlob("/pdf-translations", {
    method: "POST",
    body: formData,
  });
  await requirePdfDownload(response.blob, response.headers);
  return {
    blob: response.blob,
    filename: responseFilename(response.headers.get("Content-Disposition")),
    pageCount: optionalPositiveInteger(response.headers.get("X-PDF-Page-Count")),
    translatedSegments: optionalPositiveInteger(
      response.headers.get("X-PDF-Translated-Segments"),
    ),
  };
}

/**
 * Rejects an empty or mislabeled binary response before the UI offers it as a PDF.
 * Key parameters: response Blob and headers. Return value: promise resolved for a PDF signature.
 * Side effect: reads only the first five bytes of the in-memory response.
 */
async function requirePdfDownload(blob: Blob, headers: Headers): Promise<void> {
  const contentType = headers.get("Content-Type")?.split(";", 1)[0]?.trim().toLowerCase();
  const signature = new TextDecoder("ascii").decode(await blob.slice(0, 5).arrayBuffer());
  if (blob.size < 5 || contentType !== "application/pdf" || signature !== "%PDF-") {
    throw new Error("服务返回的文件不是有效 PDF，请稍后重试。");
  }
}

/**
 * Extracts the server-provided ASCII filename from Content-Disposition.
 * Key parameter: `value` is an optional response header. Return value: safe PDF filename.
 * Side effect: none.
 */
function responseFilename(value: string | null): string {
  const match = value?.match(/filename="?([A-Za-z0-9._-]+)"?/i);
  return match?.[1]?.toLowerCase().endsWith(".pdf") ? match[1] : "document-english.pdf";
}

/**
 * Narrows an optional integer response header for result details.
 * Key parameter: raw header text. Return value: positive integer or undefined.
 * Side effect: none.
 */
function optionalPositiveInteger(value: string | null): number | undefined {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}
