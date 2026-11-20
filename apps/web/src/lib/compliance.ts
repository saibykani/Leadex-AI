import { api, type Page } from "@/lib/api";

export const CHANNELS = ["email", "voice", "sms", "whatsapp"] as const;
export type Channel = (typeof CHANNELS)[number];
export const BASES = ["express_consent", "written_consent", "existing_relationship", "legitimate_interest", "inbound_request"] as const;

export type Consent = {
  id: string; lead_id: string; channel: string; basis: string; evidence_text: string | null; evidence_url: string | null;
  captured_at: string; withdrawn_at: string | null; withdrawn_reason: string | null; created_at: string;
};
export type Suppression = { id: string; channel: string; email_normalized: string | null; phone_normalized: string | null; reason: string; created_at: string };
export type KillSwitch = {
  id: string; organization_id: string | null; scope: "global" | "organization"; channel: string; active: boolean;
  reason: string; set_by_user_id: string | null; created_at: string; updated_at: string;
};
export type GateResult = { allowed: boolean; simulated: boolean; reasons: string[]; jurisdiction: string | null };
export type Dsr = {
  id: string; type: string; status: string; subject_email: string | null; subject_phone: string | null; lead_id: string | null;
  details: string | null; resolution: string | null; due_at: string; completed_at: string | null; created_at: string;
};

const post = (body: unknown) => ({ method: "POST", body: JSON.stringify(body) });

export const compliance = {
  consents: (page = 1) => api<Page<Consent>>(`/compliance/consents?page=${page}&page_size=50`, {}, true),
  createConsent: (b: { lead_id: string; channel: string; basis: string; evidence_text?: string; evidence_url?: string }) =>
    api<Consent>("/compliance/consents", post(b), true),
  withdrawConsent: (id: string, reason?: string) => api<Consent>(`/compliance/consents/${id}/withdraw`, post({ reason }), true),
  suppressions: (page = 1) => api<Page<Suppression>>(`/compliance/suppressions?page=${page}&page_size=50`, {}, true),
  createSuppression: (b: { channel: string; email?: string; phone?: string; reason: string }) =>
    api<Suppression>("/compliance/suppressions", post(b), true),
  deleteSuppression: (id: string) => api<void>(`/compliance/suppressions/${id}`, { method: "DELETE" }, true),
  killSwitches: () => api<KillSwitch[]>("/compliance/kill-switches", {}, true),
  createKillSwitch: (b: { channel: string; reason: string }) => api<KillSwitch>("/compliance/kill-switches", post({ ...b, scope: "organization" }), true),
  deactivateKillSwitch: (id: string) => api<KillSwitch>(`/compliance/kill-switches/${id}/deactivate`, { method: "POST" }, true),
  check: (lead_id: string, channel: string) => api<GateResult>("/compliance/check", post({ lead_id, channel }), true),
  dsrs: () => api<Page<Dsr>>("/compliance/dsr?page_size=100", {}, true),
  createDsr: (b: { type: string; subject_email?: string; subject_phone?: string; details?: string }) => api<Dsr>("/compliance/dsr", post(b), true),
  updateDsr: (id: string, status: string, resolution?: string) =>
    api<Dsr>(`/compliance/dsr/${id}`, { method: "PATCH", body: JSON.stringify({ status, resolution }) }, true),
};

export const mfaApi = {
  status: () => api<{ mfa_enabled: boolean }>("/auth/mfa"),
  setup: () => api<{ secret: string; otpauth_uri: string }>("/auth/mfa/setup", { method: "POST" }),
  verify: (code: string) => api<{ mfa_enabled: boolean }>("/auth/mfa/verify", post({ code })),
  disable: (code: string, password: string) => api<{ mfa_enabled: boolean }>("/auth/mfa/disable", post({ code, password })),
};

export type AdminOrg = { id: string; name: string; slug: string; country_code: string | null; status: string; is_platform_owner: boolean; created_at: string; deleted_at: string | null };
export type AdminUser = { id: string; email: string; full_name: string; is_active: boolean; is_superadmin: boolean; mfa_enabled: boolean; last_login_at: string | null; created_at: string };
export type Usage = {
  organizations: number; active_organizations: number; users: number; leads: number;
  per_organization: { organization_id: string; name: string; status: string; members: number; leads: number }[];
};
export type AdminAudit = { id: string; organization_id: string | null; actor_user_id: string | null; action: string; entity_type: string | null; entity_id: string | null; ip_address: string | null; created_at: string };

export const adminApi = {
  orgs: (q = "") => api<Page<AdminOrg>>(`/admin/organizations?page_size=100&q=${encodeURIComponent(q)}`),
  suspend: (id: string, reason: string) => api<AdminOrg>(`/admin/organizations/${id}/suspend`, post({ reason })),
  reactivate: (id: string) => api<AdminOrg>(`/admin/organizations/${id}/reactivate`, { method: "POST" }),
  users: (q = "") => api<Page<AdminUser>>(`/admin/users?page_size=100&q=${encodeURIComponent(q)}`),
  usage: () => api<Usage>("/admin/usage"),
  audit: (page = 1) => api<Page<AdminAudit>>(`/admin/audit-logs?page=${page}&page_size=50`),
  killSwitches: () => api<KillSwitch[]>("/admin/kill-switches"),
  createKillSwitch: (channel: string, reason: string) => api<KillSwitch>("/admin/kill-switches", post({ scope: "global", channel, reason })),
  deactivateKillSwitch: (id: string) => api<KillSwitch>(`/admin/kill-switches/${id}/deactivate`, { method: "POST" }),
};
