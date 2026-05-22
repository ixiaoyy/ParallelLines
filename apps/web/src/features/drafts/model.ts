export interface DraftPayload {
  [key: string]: unknown;
}


export interface DraftSaveRequest {
  target_type: string;
  target_id?: string;
  draft_type: string;
  data: DraftPayload;
  version: number;
}

export interface DraftResponse {
  id: string;
  user_id: string;
  target_type: string;
  target_id: string;
  draft_type: string;
  data: DraftPayload;
  version: number;
  created_at: string;
  updated_at: string;
}
