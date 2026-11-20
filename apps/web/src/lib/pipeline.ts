// Lead pipeline API: Google photo references (display-only proxy), business-owned images, outcomes, one-click run.
import { api, API_URL, ApiError, session } from "@/lib/api";
import type { Agent } from "@/lib/agents";

export type GooglePhoto = {
  name: string; width: number | null; height: number | null;
  attributions: { display_name: string | null; uri: string | null }[];
  source: "google_places"; retention_until: string | null; usable_in_website: false; notice: string;
};
export type BusinessImage = {
  id: string; business_id: string; source: "owner_supplied" | "from_business_website"; status: "pending_review" | "approved" | "rejected";
  permission_confirmed: boolean; content_type: string; size_bytes: number; origin_url: string | null; filename: string | null;
  alt: string | null; created_at: string; usable_in_website: boolean;
};
export type Outcome = {
  id: string; lead_id: string | null; agent_id: string | null; call_id: string | null; source: string;
  extraction_mode: "llm" | "rules"; model: string | null; interest: "high" | "medium" | "low" | "none" | "unknown";
  budget_min: number | null; budget_max: number | null; budget_currency: string | null; budget_evidence: string | null;
  timeline: string | null; timeline_evidence: string | null; decision_maker: string | null; decision_maker_evidence: string | null;
  objections: { objection: string; evidence: string }[] | null; next_step: string | null; summary: string;
  simulated: boolean; created_at: string; warnings: string[];
};
export type Step = {
  key: "business" | "photos" | "lead" | "website" | "agent" | "call"; status: "done" | "skipped" | "blocked" | "failed" | "not_requested";
  message: string; at: string; reasons?: string[]; fixes?: string[]; preview_path?: string; website_id?: string;
  lead_id?: string; call_id?: string; call_status?: string; simulated?: boolean; error?: { code: string; detail: string };
};
export type Run = {
  id: string; business_id: string; lead_id: string | null; website_project_id: string | null; agent_id: string | null;
  call_id: string | null; status: "running" | "completed" | "needs_action" | "failed"; steps: Step[];
  created_at: string; updated_at: string; outcome: Outcome | null;
};
export type Package = { name: string; min: number; max: number; currency: string; description?: string | null };
export type Turn = { role: "user" | "assistant"; text: string };

const j = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = {};
  if (session.access) h.Authorization = `Bearer ${session.access}`;
  if (session.org) h["X-Organization-Id"] = session.org;
  return h;
}

async function blobUrl(path: string): Promise<{ url: string; headers: Headers }> {
  const r = await fetch(`${API_URL}/api/v1${path}`, { headers: authHeaders() });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new ApiError(r.status, body?.error?.code ?? "error", body?.error?.message ?? "Image unavailable");
  }
  return { url: URL.createObjectURL(await r.blob()), headers: r.headers };
}

export const pipelineApi = {
  googlePhotos: (bid: string) => api<{ photos: GooglePhoto[]; notice: string }>(`/businesses/${bid}/google-photos`, {}, true),
  /** Streams a Google photo through the Leadex proxy for in-app display only (object URL; not stored). */
  googlePhotoUrl: (bid: string, name: string, maxWidth = 640) =>
    blobUrl(`/businesses/${bid}/google-photos/media?name=${encodeURIComponent(name)}&max_width=${maxWidth}`).then((r) => r.url),
  images: (bid: string) => api<BusinessImage[]>(`/businesses/${bid}/images`, {}, true),
  imageUrl: (bid: string, iid: string) => blobUrl(`/businesses/${bid}/images/${iid}/content`).then((r) => r.url),
  async upload(bid: string, file: File, permissionConfirmed: boolean): Promise<BusinessImage> {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("permission_confirmed", permissionConfirmed ? "true" : "false");
    const r = await fetch(`${API_URL}/api/v1/businesses/${bid}/images`, { method: "POST", body: fd, headers: authHeaders() });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new ApiError(r.status, body?.error?.code ?? "error", body?.error?.message ?? "Upload failed");
    return body as BusinessImage;
  },
  importWebsite: (bid: string) =>
    api<{ imported: BusinessImage[]; skipped: { url: string; reason: string }[]; notice: string }>(`/businesses/${bid}/images/import-website`, j("POST"), true),
  approve: (bid: string, iid: string) => api<BusinessImage>(`/businesses/${bid}/images/${iid}/approve`, j("POST", { permission_confirmed: true }), true),
  reject: (bid: string, iid: string) => api<BusinessImage>(`/businesses/${bid}/images/${iid}/reject`, j("POST"), true),
  remove: (bid: string, iid: string) => api<void>(`/businesses/${bid}/images/${iid}`, j("DELETE"), true),
  packages: () => api<{ packages: Package[] }>("/pipeline/packages", {}, true).then((r) => r.packages),
  savePackages: (packages: Package[]) => api<{ packages: Package[] }>("/pipeline/packages", j("PUT", { packages }), true),
  budgetAgent: (business_name?: string) => api<Agent>("/pipeline/budget-agent", j("POST", { business_name }), true),
  extract: (b: { transcript: Turn[]; lead_id?: string; agent_id?: string; call_id?: string; source: "test_lab" | "browser_voice" | "call" }) =>
    api<Outcome>("/pipeline/outcomes/extract", j("POST", b), true),
  outcomes: (q: { lead_id?: string; agent_id?: string }) =>
    api<Outcome[]>(`/pipeline/outcomes?${new URLSearchParams(Object.entries(q).filter(([, v]) => v) as [string, string][])}`, {}, true),
  run: (b: { business_id: string; template_key?: string; image_ids?: string[]; generate_website?: boolean; agent_id?: string; place_call?: boolean }) =>
    api<Run>("/pipeline/run", j("POST", b), true),
  runs: (business_id?: string) => api<Run[]>(`/pipeline/runs${business_id ? `?business_id=${business_id}` : ""}`, {}, true),
};
