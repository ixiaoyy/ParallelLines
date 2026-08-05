export interface PdfTranslationCapabilities {
  ai_enabled: boolean;
  max_bytes: number;
  max_pages: number;
  privacy_notice: string;
}

export interface PdfTranslationDownload {
  blob: Blob;
  filename: string;
  pageCount?: number;
  translatedSegments?: number;
}
