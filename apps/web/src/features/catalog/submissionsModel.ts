export type CatalogSubmissionStatus = "pending" | "approved" | "rejected";

export interface CatalogSubmissionPayload {
  category_name: string;
  project_name: string;
  url: string;
  author_name: string | null;
  contact: string | null;
  cover: File | null;
}

export interface CatalogSubmissionCreateResult {
  id: string;
  status: "pending";
}

export interface AdminCatalogSubmission {
  id: string;
  category_name: string;
  project_name: string;
  url: string;
  author_name: string | null;
  contact: string | null;
  cover_url: string | null;
  status: CatalogSubmissionStatus;
  project_id: string | null;
  reviewed_by_id: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export type AdminCatalogSubmissions = AdminCatalogSubmission[];
