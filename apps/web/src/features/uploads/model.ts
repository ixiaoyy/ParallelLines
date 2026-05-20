export type UploadKind = "post_attachment" | "avatar";

export interface UploadResponse {
  id: string;
  url: string;
  original_filename: string;
  media_type: string;
  byte_size: number;
  kind: UploadKind | string;
  status: "temporary" | "attached" | "avatar" | "deleted" | string;
  is_image: boolean;
  created_at: string;
}

export function toMarkdownUpload(upload: UploadResponse, absoluteUrl: string): string {
  const label = upload.original_filename.replace(/[\]\n\r]/g, " ").trim() || "upload";
  return upload.is_image ? `![${label}](${absoluteUrl})` : `[${label}](${absoluteUrl})`;
}
