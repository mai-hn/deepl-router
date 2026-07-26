export interface UpstreamKindMeta {
  kind: string;
  label: string;
  default_endpoint: string;
  endpoint_help: string;
  key_label: string;
  key_placeholder: string;
  needs_secret: boolean;
  secret_label: string | null;
  secret_placeholder: string | null;
  needs_region: boolean;
  region_label: string | null;
  region_placeholder: string | null;
  quota_type: "characters" | "balance" | null;
  color: string;
  sort_order: number;
  batch_aliases: string[];
}

export interface Quota {
  type: "characters" | "balance";
  used?: number | null;
  limit?: number | null;
  amount?: number | null;
  currency?: string | null;
}

export interface HealthEvent {
  provider_id: number;
  status: "healthy" | "unhealthy";
  latency_ms: number | null;
  source: string;
  created_at: string;
}

export interface Provider {
  id: number;
  name: string;
  kind: string;
  endpoint: string;
  key_hint: string;
  region: string;
  priority: number;
  weight: number;
  enabled: boolean;
  timeout_seconds: number;
  last_status: "unknown" | "healthy" | "unhealthy";
  last_latency_ms: number | null;
  last_error: string | null;
  quota: Quota | null;
  quota_checked_at: string | null;
  quota_error: string | null;
  quota_limit: number | null;
  quota_exceeded: boolean;
  health_history: HealthEvent[];
  created_at: string;
  updated_at: string;
}

export interface ProviderInput {
  name: string;
  kind: string;
  endpoint: string;
  api_key?: string;
  api_secret?: string;
  region?: string;
  priority?: number;
  weight?: number;
  enabled?: boolean;
  timeout_seconds?: number;
  quota_limit?: number | null;
}

export interface Settings {
  routing_mode: string;
  fallback_enabled: boolean;
  downstream_key: string;
  downstream_key_hint: string;
}

export interface RequestLogSummary {
  id: number;
  request_id: string;
  route: string;
  provider: string | null;
  status: string;
  latency_ms: number | null;
  error: string | null;
  created_at: string;
  text_preview: string;
  attempt_count: number;
}

export interface RequestLogDetail {
  id: number;
  request_id: string;
  route: string;
  downstream_request: unknown;
  upstream_attempts: unknown[];
  response_body: unknown;
  provider: string | null;
  status: string;
  latency_ms: number | null;
  error: string | null;
  created_at: string;
}

export interface DashboardStats {
  providers: { total: number; enabled: number; healthy: number; quota_exceeded: number };
  requests: { total: number; last_24h: number; success_24h: number; failed_24h: number; avg_latency_24h: number | null };
}

export interface CheckResult {
  ok: boolean;
  latency_ms: number;
  error?: string;
}

export interface QuotaQueryResult {
  ok?: boolean;
  provider_id: number;
  quota?: Quota;
  error?: string;
}

export interface TranslateResponse {
  data: string | string[];
  translations: { text: string; detected_source_lang: string | null }[];
  providers: string[];
}
