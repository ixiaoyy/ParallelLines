import type { PersonaKind } from "@/entities/user/model";

export interface MigrationUserRecord {
  username: string;
  email: string;
  display_name?: string | null;
  is_persona?: boolean;
  persona_kind?: PersonaKind | null;
}

export interface MigrationBoardRecord {
  slug: string;
  name: string;
  description?: string;
  color?: string;
}

export interface MigrationTopicRecord {
  external_id?: string | null;
  board_slug: string;
  author_username: string;
  title: string;
  slug?: string | null;
  tags?: string[];
  raw_md?: string;
  created_at?: string | null;
}

export interface MigrationPostRecord {
  topic_external_id?: string | null;
  topic_slug?: string | null;
  board_slug: string;
  author_username: string;
  post_number: number;
  raw_md: string;
  created_at?: string | null;
}

export interface MigrationImportRequest {
  source?: string;
  users?: MigrationUserRecord[];
  boards?: MigrationBoardRecord[];
  topics?: MigrationTopicRecord[];
  posts?: MigrationPostRecord[];
}

export interface MigrationRowResult {
  resource: string;
  key: string;
  action: string;
  message: string;
}

export interface MigrationImportResponse {
  dry_run: boolean;
  source: string;
  created: number;
  updated: number;
  skipped: number;
  errors: number;
  rows: MigrationRowResult[];
}

export interface MigrationExportResponse {
  exported_at: string;
  users: Record<string, unknown>[];
  boards: Record<string, unknown>[];
  topics: Record<string, unknown>[];
  posts: Record<string, unknown>[];
  tags: Record<string, unknown>[];
}
