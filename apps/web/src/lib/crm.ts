// Typed client for the CRM module (/api/v1/leads, /api/v1/dashboard).
import { api, API_URL, ApiError, session, type Page } from "@/lib/api";
import type { Tone } from "@/components/ui";

export type Lead = {
  id: string; organization_id: string; business_name: string; industry: string | null; country: string | null;
  city: string | null; phone: string | null; email: string | null; website: string | null; source: string;
  status: LeadStatus; score: number | null; owner_user_id: string | null; consent_reference: string | null;
  custom_fields: Record<string, unknown> | null; created_at: string; updated_at: string;
};
export type LeadInput = Partial<Pick<Lead, "industry" | "country" | "city" | "phone" | "email" | "website" | "score" | "owner_user_id" | "source">> & { business_name?: string };
export type Note = { id: string; lead_id: string; author_user_id: string | null; body: string; created_at: string };
export type Task = { id: string; lead_id: string; title: string; due_at: string | null; completed_at: string | null; assignee_user_id: string | null; created_at: string };
export type Activity = { id: string; lead_id: string; actor_user_id: string | null; type: string; data: Record<string, unknown> | null; created_at: string };
export type DashboardSummary = { total_leads: number; by_status: Record<string, number>; open_tasks: number; overdue_tasks: number };

// Mirrors app/modules/crm/service.py — the backend remains the source of truth and rejects invalid moves.
export const STATUSES = [
  "discovered", "unverified", "verified", "pending_consent", "approved_for_outreach", "contacted",
  "interested", "qualified", "meeting_scheduled", "proposal_sent", "negotiation", "converted", "lost",
  "callback_requested", "not_interested", "do_not_contact", "suppressed",
] as const;
export type LeadStatus = (typeof STATUSES)[number];
const TERMINAL: LeadStatus[] = ["do_not_contact", "suppressed"];
const T: Record<LeadStatus, LeadStatus[]> = {
  discovered: ["unverified", "verified", "lost"],
  unverified: ["verified", "lost"],
  verified: ["pending_consent", "approved_for_outreach", "lost"],
  pending_consent: ["approved_for_outreach", "not_interested", "lost"],
  approved_for_outreach: ["contacted", "lost"],
  contacted: ["interested", "callback_requested", "not_interested", "qualified", "lost"],
  callback_requested: ["contacted", "interested", "not_interested", "lost"],
  interested: ["qualified", "meeting_scheduled", "not_interested", "lost"],
  qualified: ["meeting_scheduled", "proposal_sent", "not_interested", "lost"],
  meeting_scheduled: ["qualified", "proposal_sent", "not_interested", "lost"],
  proposal_sent: ["negotiation", "converted", "lost"],
  negotiation: ["proposal_sent", "converted", "lost"],
  converted: [], lost: ["verified"], not_interested: ["callback_requested", "lost"], do_not_contact: [], suppressed: [],
};
export function allowedNext(s: LeadStatus): LeadStatus[] {
  if (TERMINAL.includes(s)) return T[s];
  return [...T[s], ...TERMINAL.filter((t) => t !== s)];
}
export const CONSENT_REQUIRED: LeadStatus[] = ["approved_for_outreach"];
export const FUNNEL: LeadStatus[] = ["discovered", "verified", "approved_for_outreach", "contacted", "interested", "qualified", "meeting_scheduled", "proposal_sent", "negotiation", "converted"];

export const statusLabel = (s: string) => s.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
export function statusTone(s: string): Tone {
  if (s === "converted") return "success";
  if (["lost", "not_interested", "do_not_contact", "suppressed"].includes(s)) return "danger";
  if (["pending_consent", "callback_requested", "unverified"].includes(s)) return "warning";
  if (["qualified", "meeting_scheduled", "proposal_sent", "negotiation"].includes(s)) return "violet";
  if (["approved_for_outreach", "contacted", "interested", "verified"].includes(s)) return "accent";
  return "neutral";
}

/** Error carrying the backend's structured `details` (e.g. duplicate_lead.existing_lead_id). */
export class CrmError extends ApiError {
  constructor(status: number, code: string, message: string, public details: unknown) { super(status, code, message); }
}

// Like api(), but preserves error details. Falls back to api() on 401 so token refresh logic stays in one place.
async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (session.access) headers.set("Authorization", `Bearer ${session.access}`);
  if (session.org) headers.set("X-Organization-Id", session.org);
  const r = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers });
  if (r.status === 401) return api<T>(path, init, true);
  if (r.status === 204) return undefined as T;
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const e = body?.error ?? {};
    const detail = Array.isArray(e.details) && e.details[0]?.msg ? `: ${e.details[0].msg}` : "";
    throw new CrmError(r.status, e.code ?? "error", (e.message ?? "Request failed") + detail, e.details);
  }
  return body as T;
}

export type LeadQuery = { page?: number; page_size?: number; status?: string[]; q?: string; owner?: string; sort?: string };
const json = (b: unknown) => JSON.stringify(b);

export const crm = {
  listLeads(p: LeadQuery) {
    const qs = new URLSearchParams();
    if (p.page) qs.set("page", String(p.page));
    if (p.page_size) qs.set("page_size", String(p.page_size));
    p.status?.forEach((s) => qs.append("status", s));
    if (p.q?.trim()) qs.set("q", p.q.trim());
    if (p.owner) qs.set("owner", p.owner);
    if (p.sort) qs.set("sort", p.sort);
    return req<Page<Lead>>(`/leads?${qs}`);
  },
  getLead: (id: string) => req<Lead>(`/leads/${id}`),
  createLead: (b: LeadInput) => req<Lead>("/leads", { method: "POST", body: json(b) }),
  updateLead: (id: string, b: LeadInput) => req<Lead>(`/leads/${id}`, { method: "PATCH", body: json(b) }),
  deleteLead: (id: string) => req<void>(`/leads/${id}`, { method: "DELETE" }),
  changeStatus: (id: string, b: { status: string; consent_reference?: string; reason?: string; admin_override?: boolean }) =>
    req<Lead>(`/leads/${id}/status`, { method: "POST", body: json(b) }),
  notes: (id: string) => req<Note[]>(`/leads/${id}/notes`),
  addNote: (id: string, body: string) => req<Note>(`/leads/${id}/notes`, { method: "POST", body: json({ body }) }),
  tasks: (id: string) => req<Task[]>(`/leads/${id}/tasks`),
  addTask: (id: string, b: { title: string; due_at?: string | null; assignee_user_id?: string | null }) =>
    req<Task>(`/leads/${id}/tasks`, { method: "POST", body: json(b) }),
  updateTask: (taskId: string, b: { completed?: boolean; title?: string }) =>
    req<Task>(`/leads/tasks/${taskId}`, { method: "PATCH", body: json(b) }),
  activities: (id: string, page = 1) => req<Page<Activity>>(`/leads/${id}/activities?page=${page}&page_size=50`),
  summary: () => req<DashboardSummary>("/dashboard/summary"),
};

export function duplicateLeadId(e: unknown): string | null {
  if (e instanceof CrmError && e.code === "duplicate_lead" && e.details && typeof e.details === "object") {
    const id = (e.details as { existing_lead_id?: unknown }).existing_lead_id;
    return typeof id === "string" ? id : null;
  }
  return null;
}

export const fmtDate = (s: string) => new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
export const fmtDateTime = (s: string) => new Date(s).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
export function timeAgo(s: string) {
  const d = (Date.now() - new Date(s).getTime()) / 1000;
  if (d < 60) return "just now";
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  if (d < 604800) return `${Math.floor(d / 86400)}d ago`;
  return fmtDate(s);
}
