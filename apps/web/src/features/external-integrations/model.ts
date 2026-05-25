export interface ExternalIntegrationConfig {
  [key: string]: string | number | boolean | null | undefined;
}

export interface ExternalIntegrationInfo {
  provider: string;
  enabled: boolean;
  config: Record<string, unknown>;
  required_config: string[];
  status: string;
  issues: string[];
  last_checked_at: string | null;
  last_error: string | null;
  updated_at: string | null;
}

export interface ExternalIntegrationUpdateRequest {
  enabled: boolean;
  config: ExternalIntegrationConfig;
}

export interface ExternalIntegrationEventInfo {
  id: string;
  provider: string;
  event_id: string;
  event_type: string;
  action: string | null;
  status: string;
  signature_valid: boolean;
  retry_count: number;
  max_retries: number;
  next_retry_at: string | null;
  processed_at: string | null;
  last_error: string | null;
  linked_resource_type: string | null;
  linked_resource_id: string | null;
  external_url: string | null;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface GitHubIssuePreview {
  owner: string;
  repo: string;
  number: number;
  title: string;
  state: string | null;
  url: string;
  source: "webhook_cache" | "parsed_url";
}

export const EXTERNAL_PROVIDER_LABELS: Record<string, string> = {
  github: "GitHub",
  patreon: "Patreon",
  zendesk: "Zendesk",
};

export function providerLabel(provider: string): string {
  return EXTERNAL_PROVIDER_LABELS[provider] ?? provider;
}

export function integrationStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    disabled: "未启用",
    error: "异常",
    healthy: "健康",
    misconfigured: "缺少配置",
  };
  return labels[status] ?? status;
}
