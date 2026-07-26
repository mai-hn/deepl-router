import { request } from "./client";
import type {
  CheckResult,
  BatchCheckResult,
  DashboardStats,
  Provider,
  ProviderInput,
  QuotaQueryResult,
  RequestLogDetail,
  RequestLogSummary,
  Settings,
  TranslateResponse,
  UpstreamKindMeta,
} from "./types";

export const listUpstreamKinds = () => request<UpstreamKindMeta[]>("/api/upstream-kinds");
export const getDashboard = () => request<DashboardStats>("/api/dashboard");

export const listProviders = () => request<Provider[]>("/api/providers");
export const createProvider = (payload: ProviderInput) =>
  request<Provider>("/api/providers", { method: "POST", body: JSON.stringify(payload) });
export const updateProvider = (id: number, payload: Partial<ProviderInput>) =>
  request<Provider>(`/api/providers/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
export const deleteProvider = (id: number) => request<void>(`/api/providers/${id}`, { method: "DELETE" });
export const createProvidersBatch = (payload: { lines: string; priority: number; weight: number; timeout_seconds: number }) =>
  request<Provider[]>("/api/providers/batch", { method: "POST", body: JSON.stringify(payload) });
export const checkProvider = (id: number) => request<CheckResult>(`/api/providers/${id}/check`, { method: "POST" });
export const checkAllProviders = () => request<BatchCheckResult>("/api/providers/check", { method: "POST" });
export const disableUnhealthy = (providerIds: number[]) =>
  request<{ count: number; provider_ids: number[] }>("/api/providers/batch/disable-unhealthy", {
    method: "POST",
    body: JSON.stringify({ provider_ids: providerIds }),
  });
export const deleteUnhealthy = (providerIds: number[]) =>
  request<{ count: number; provider_ids: number[] }>("/api/providers/batch/delete-unhealthy", {
    method: "POST",
    body: JSON.stringify({ provider_ids: providerIds }),
  });

export const queryProviderQuota = (id: number) =>
  request<QuotaQueryResult>(`/api/providers/${id}/quota`, { method: "POST" });
export const queryAllQuota = () => request<QuotaQueryResult[]>("/api/quota", { method: "POST" });

export const getSettings = () => request<Settings>("/api/settings");
export const updateSettings = (payload: Partial<{ routing_mode: string; fallback_enabled: boolean; downstream_key: string }>) =>
  request<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(payload) });

export const listLogs = (limit = 50) => request<RequestLogSummary[]>(`/api/logs?limit=${limit}`);
export const getLog = (id: number) => request<RequestLogDetail>(`/api/logs/${id}`);

export const translate = (payload: { text: string; target_lang: string; source_lang?: string }) =>
  request<TranslateResponse>("/translate", { method: "POST", body: JSON.stringify(payload) });
