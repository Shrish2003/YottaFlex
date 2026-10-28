import type { Action, Excursion, ExcursionDetail, GenerateRequest, Generation, Quality, Shipment, Validation, PageResponse } from "./types";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
type ApiErrorBody = { error?: { code?: string; message?: string; details?: string[] } };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try { response = await fetch(`${BASE_URL}${path}`, { ...init, headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers } }); }
  catch { throw new Error("Unable to reach the YottaFlex API. Confirm the backend is running and the configured URL is correct."); }
  if (!response.ok) {
    const body = await response.json().catch(() => null) as ApiErrorBody | null;
    const error = body?.error;
    throw new Error(error?.message || `API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}
const query = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => value !== undefined && value !== "" && search.set(key, String(value)));
  return search.toString();
};
export const api = {
  shipments: (params: Record<string, string | number | undefined> = {}) => request<PageResponse<Shipment>>(`/api/shipments?${query({ page: 1, page_size: 25, ...params })}`),
  shipment: (id: string) => request<Shipment>(`/api/shipments/${encodeURIComponent(id)}`),
  shipmentSummary: (id: string) => request<{ shipment_id: string; reading_count: number; telemetry_gap_count: number; excursions_by_status: Record<string, number>; excursions_by_severity: Record<string, number>; open_corrective_action_count: number; custody_event_count: number; data_quality_status: string }>(`/api/shipments/${encodeURIComponent(id)}/summary`),
  excursions: (params: Record<string, string | number | undefined> = {}) => request<PageResponse<Excursion>>(`/api/excursions?${query({ page: 1, page_size: 25, ...params })}`),
  excursion: (id: string) => request<ExcursionDetail>(`/api/excursions/${encodeURIComponent(id)}`),
  action: (id: string, payload: { assigned_to: string; action_type: string; description: string }) => request<Action>(`/api/excursions/${encodeURIComponent(id)}/actions`, { method: "POST", body: JSON.stringify(payload) }),
  quality: () => request<Quality>("/api/quality/summary"),
  validate: () => request<Validation>("/api/validate", { method: "POST" }),
  generate: (payload: GenerateRequest) => request<Generation>("/api/generate", { method: "POST", body: JSON.stringify(payload) }),
  exportUrl: (dataset: string, format = "csv") => `${BASE_URL}/api/exports/${dataset}?format=${format}`,
};
