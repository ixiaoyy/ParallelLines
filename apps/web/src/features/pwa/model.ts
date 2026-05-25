export interface PushSubscriptionKeysPayload {
  p256dh: string;
  auth: string;
}

export interface PushSubscriptionRequest {
  endpoint: string;
  keys: PushSubscriptionKeysPayload;
  user_agent?: string | null;
}

export interface PushSubscriptionInfo {
  id: string;
  endpoint_excerpt: string;
  enabled: boolean;
  user_agent: string | null;
  last_sent_at: string | null;
  disabled_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PushSubscriptionState {
  subscription: PushSubscriptionInfo | null;
  supported: boolean;
  preference_hint: string;
}
