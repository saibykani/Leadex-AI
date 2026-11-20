import { API_URL, api, session, type Page } from "@/lib/api";

export type Theme = {
  primary: string; accent: string; bg: string; surface: string; text: string; muted: string;
  gradient: string; hero: string; services_layout: string; radius: string; hero_cta?: string;
};
export type Template = { key: string; industry: string; name: string; sections: { type: string; heading: string }[]; theme: Theme };
export type Item = { title?: string | null; description?: string | null };
export type Section = {
  type: "hero" | "services" | "about" | "gallery" | "contact" | "cta";
  heading: string; body?: string | null; enabled: boolean; cta_label?: string | null; items?: Item[] | null;
};
export type Business = {
  name: string; industry_label?: string | null; tagline?: string | null; description?: string | null; city?: string | null;
  address?: string | null; country?: string | null; phone?: string | null; email?: string | null; hours?: string | null;
  whatsapp_number?: string | null; whatsapp_authorized: boolean;
};
export type Content = { business: Business; seo: { title: string; description: string }; sections: Section[] };
export type Project = {
  id: string; name: string; template_key: string; status: "draft" | "preview" | "approved" | "published";
  business_id: string | null; lead_id: string | null; current_version_id: string | null;
  approved_version_id: string | null; published_version_id: string | null;
  custom_domain: string | null; domain_verification_status: string; created_at: string; updated_at: string;
};
export type DomainInfo = {
  domain: string | null; status: "none" | "pending" | "verified"; verified_at: string | null;
  record_type: string; record_name: string | null; record_value: string | null; message: string | null;
};
export type ProjectDetail = Project & {
  current_version_number: number | null; content: Content | null; rendered_html: string | null;
  generation_mode: string | null; preview_path: string; published_path: string | null;
};
export type Version = { id: string; number: number; note: string | null; generation_mode: string; created_by: string | null; created_at: string };
export type Feedback = { id: string; version_id: string | null; name: string; message: string; approved: boolean; created_at: string };
export type Deployment = { id: string; version_id: string; status: string; target: string; url: string; deployed_at: string; rolled_back_from: string | null };
export type BusinessFacts = {
  name: string; industry?: string; tagline?: string; description?: string; services?: string[]; city?: string;
  address?: string; phone?: string; email?: string; hours?: string; whatsapp_number?: string; whatsapp_authorized?: boolean;
};

const j = (body: unknown) => ({ method: "POST", body: JSON.stringify(body) });

export const websites = {
  templates: () => api<Template[]>("/websites/templates", {}, true),
  list: () => api<Page<Project>>("/websites?page_size=100", {}, true),
  get: (id: string) => api<ProjectDetail>(`/websites/${id}`, {}, true),
  generate: (body: { template_key: string; business?: BusinessFacts; lead_id?: string; name?: string }) =>
    api<ProjectDetail>("/websites/generate", j(body), true),
  save: (id: string, body: { content?: Content; note?: string; template_key?: string; name?: string }) =>
    api<ProjectDetail>(`/websites/${id}`, { method: "PATCH", body: JSON.stringify(body) }, true),
  versions: (id: string) => api<Version[]>(`/websites/${id}/versions`, {}, true),
  restore: (id: string, vid: string) => api<ProjectDetail>(`/websites/${id}/versions/${vid}/restore`, j({}), true),
  previewLink: (id: string, rotate = false) => api<{ token: string; path: string }>(`/websites/${id}/preview-link`, j({ rotate }), true),
  feedback: (id: string) => api<Feedback[]>(`/websites/${id}/feedback`, {}, true),
  deployments: (id: string) => api<Deployment[]>(`/websites/${id}/deployments`, {}, true),
  domain: (id: string) => api<DomainInfo>(`/websites/${id}/domain`, {}, true),
  setDomain: (id: string, domain: string) => api<DomainInfo>(`/websites/${id}/domain`, { method: "PUT", body: JSON.stringify({ domain }) }, true),
  verifyDomain: (id: string) => api<DomainInfo>(`/websites/${id}/domain/verify`, j({}), true),
  removeDomain: (id: string) => api<unknown>(`/websites/${id}/domain`, { method: "DELETE" }, true),
  approve: (id: string) => api<ProjectDetail>(`/websites/${id}/approve`, j({}), true),
  publish: (id: string) => api<Deployment>(`/websites/${id}/publish`, j({}), true),
  rollback: (id: string, version_id: string) => api<Deployment>(`/websites/${id}/rollback`, j({ version_id }), true),
  /** Server-rendered HTML for unsaved editor content (returns text/html, so not via api<T>). */
  async render(id: string, content: Content): Promise<string> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (session.access) headers.Authorization = `Bearer ${session.access}`;
    if (session.org) headers["X-Organization-Id"] = session.org;
    const r = await fetch(`${API_URL}/api/v1/websites/${id}/render`, { method: "POST", headers, body: JSON.stringify({ content }) });
    if (!r.ok) throw new Error("Preview render failed");
    return r.text();
  },
};

export const absolute = (path: string) => `${API_URL}${path}`;

export const STATUS_STYLE: Record<Project["status"], string> = {
  draft: "bg-neutral-100 text-neutral-700",
  preview: "bg-blue-50 text-blue-700",
  approved: "bg-amber-50 text-amber-700",
  published: "bg-green-50 text-green-700",
};
