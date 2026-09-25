export interface AdminCatalogProject {
  id: string;
  category_id: string;
  slug: string;
  name: string;
  url: string;
  kind: "external" | "internal";
  description: string | null;
  author_name: string | null;
  author_url: string | null;
  icon_upload_id: string | null;
  icon_url: string | null;
  sort_order: number;
  is_visible: boolean;
  created_at: string;
  updated_at: string;
  average_score: number | null;
  rating_count: number;
  rating_score_sum: number;
  my_score: number | null;
}

export interface AdminCatalogCategory {
  id: string;
  slug: string;
  name: string;
  icon_upload_id: string | null;
  icon_url: string | null;
  sort_order: number;
  is_visible: boolean;
  created_at: string;
  updated_at: string;
  projects: AdminCatalogProject[];
}

export interface AdminCatalog {
  categories: AdminCatalogCategory[];
}

export interface CategoryDraftPayload {
  slug: string;
  name: string;
  icon_upload_id: string | null;
  sort_order: number;
  is_visible: boolean;
}

export interface ProjectDraftPayload {
  category_id: string;
  slug: string;
  name: string;
  url: string;
  kind: "external" | "internal";
  description: string | null;
  author_name: string | null;
  icon_upload_id: string | null;
  sort_order: number;
  is_visible: boolean;
}
