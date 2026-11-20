import { api, API_URL, ApiError, session, type Page } from "@/lib/api";

export type SourceStatus = {
  source: string; label: string; status: "configured" | "not_configured" | "available" | string;
  simulated: boolean; detail: string | null; supports_search: boolean;
};
export type Sources = { sources: SourceStatus[]; daily_request_budget: number; requests_used_today: number };
export type Criteria = {
  source: string; country?: string; state?: string; city?: string; locality?: string; postal_code?: string;
  radius_km?: number; industry?: string; category?: string; name?: string; website_status?: string; limit?: number;
};
export type SearchJob = {
  id: string; source: string; status: "queued" | "running" | "completed" | "failed"; criteria: Criteria & Record<string, unknown>;
  results_count: number; new_count: number; duplicate_count: number; cost_units: number; error: string | null;
  is_simulated: boolean; saved_search_id: string | null; created_at: string; started_at: string | null; finished_at: string | null;
};
export type Business = {
  id: string; name: string | null; industry: string | null; category: string | null; address: string | null;
  country: string | null; state: string | null; city: string | null; locality: string | null; postal_code: string | null;
  lat: number | null; lng: number | null; phone: string | null; email: string | null; website: string | null;
  google_place_id: string | null; source: string; is_simulated: boolean; verification_status: string;
  website_status: string; contact_permission_status: string; lead_id: string | null; collected_at: string;
  last_verified_at: string | null; created_at: string;
};
export type Finding = { check: string; label?: string; passed: boolean; points: number; max_points: number; explanation: string };
export type WebsiteAudit = {
  id: string; url: string; final_url: string | null; reachable: boolean; http_status: number | null;
  ssl_valid: boolean | null; mobile_viewport: boolean | null; load_ms: number | null; has_contact_info: boolean | null;
  has_cta: boolean | null; has_title: boolean | null; has_meta_description: boolean | null;
  broken_links_checked: number; broken_links_found: number; score: number | null; findings: Finding[] | null;
  error: string | null; attempts: number; created_at: string;
};
export type Provenance = {
  id: string; field: string; value: string | null; source: string; source_ref: string | null;
  collected_at: string; retention_until: string | null; purged_at: string | null;
};
export type BusinessDetail = {
  business: Business;
  sources: { id: string; source: string; source_ref: string | null; is_simulated: boolean; search_job_id: string | null; collected_at: string }[];
  provenance: Provenance[];
  audits: WebsiteAudit[];
  verifications: { id: string; method: string; result: string; details: Record<string, unknown> | null; created_at: string }[];
};

export const WEBSITE_STATUSES = ["unknown", "has_website", "no_website_listed", "reachable", "unreachable_retry"] as const;
export const websiteStatusLabel: Record<string, string> = {
  unknown: "Unknown", has_website: "Has website", no_website_listed: "No website listed",
  reachable: "Reachable", unreachable_retry: "Unreachable (retry)",
};

const qs = (p: Record<string, string | number | undefined | null>) => {
  const s = new URLSearchParams();
  Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") s.set(k, String(v)); });
  const out = s.toString();
  return out ? `?${out}` : "";
};

export const discovery = {
  sources: () => api<Sources>("/discovery/sources", {}, true),
  search: (criteria: Criteria) => api<SearchJob>("/discovery/search", { method: "POST", body: JSON.stringify({ criteria }) }, true),
  jobs: (page = 1) => api<Page<SearchJob>>(`/discovery/jobs${qs({ page, page_size: 10 })}`, {}, true),
  businesses: (f: { page?: number; q?: string; website_status?: string; industry?: string; city?: string; job_id?: string }) =>
    api<Page<Business>>(`/businesses${qs({ page_size: 25, ...f })}`, {}, true),
  business: (id: string) => api<BusinessDetail>(`/businesses/${id}`, {}, true),
  audit: (id: string) => api<WebsiteAudit>(`/businesses/${id}/audit`, { method: "POST" }, true),
  convert: (id: string) => api<{ business_id: string; lead_id: string }>(`/businesses/${id}/convert-to-lead`, { method: "POST" }, true),

  // Multipart and file download bypass api() (it forces a JSON content type).
  async importCsv(file: File): Promise<SearchJob> {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`${API_URL}/api/v1/discovery/import`, { method: "POST", body: fd, headers: authHeaders() });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new ApiError(r.status, body?.error?.code ?? "error", body?.error?.message ?? "Import failed");
    return body as SearchJob;
  },
  async exportCsv(filters: Record<string, string | undefined> = {}) {
    const r = await fetch(`${API_URL}/api/v1/discovery/export${qs(filters)}`, { headers: authHeaders() });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new ApiError(r.status, body?.error?.code ?? "error", body?.error?.message ?? "Export failed");
    }
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement("a");
    a.href = url; a.download = "businesses.csv"; a.click();
    URL.revokeObjectURL(url);
  },
};

function authHeaders(): HeadersInit {
  const h: Record<string, string> = {};
  if (session.access) h.Authorization = `Bearer ${session.access}`;
  if (session.org) h["X-Organization-Id"] = session.org;
  return h;
}
