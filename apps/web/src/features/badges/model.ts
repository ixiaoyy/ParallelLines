export interface BadgeResponse {
  id: string;
  slug: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  trust_level_required: number;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserBadgeResponse {
  id: string;
  badge_id: string;
  badge_slug: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  source_type: string;
  source_id: string | null;
  granted_by_id: string | null;
  granted_at: string;
  revoked_at: string | null;
  revoked_by_id: string | null;
  revoke_reason: string | null;
  note: string | null;
}

export interface BadgeGrantRequest {
  badge_slug: string;
  note?: string | null;
}

export interface BadgeRevokeRequest {
  reason?: string | null;
}
