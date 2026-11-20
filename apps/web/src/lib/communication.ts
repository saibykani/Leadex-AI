import { api, type Page } from "@/lib/api";

export type EmailAccount = {
  id: string; provider: "gmail" | "outlook" | "smtp"; address: string; display_name: string | null;
  status: string; credentials_encrypted: boolean; last_error: string | null; created_at: string;
};
export type ProviderStatus = { gmail: string; outlook: string; smtp: string; whatsapp: string; outbound_mode: string };
export type EmailTemplate = {
  id: string; name: string; subject: string; html: string; text: string | null; variables: string[] | null;
  created_at: string; updated_at: string;
};
export type Preview = { subject: string; html: string; text: string; variables: string[]; missing_variables: string[] };
export type EmailMessage = {
  id: string; campaign_id: string | null; lead_id: string | null; direction: string; status: string;
  step_index: number | null; from_address: string | null; to_address: string | null; subject: string | null;
  gate_reasons: string[] | null; provider_message_id: string | null; error: string | null; created_at: string;
};
export type EmailAnalytics = {
  total: number; by_status: Record<string, number>; sent: number; delivered: number; bounced: number;
  replied: number; simulated: number; blocked: number; inbound: number;
};
export type WAAccount = { id: string; phone_number_id: string; display_phone: string | null; status: string };
export type WATemplate = { id: string; name: string; language: string; category: string; body: string; status: string; created_at: string };
export type Conversation = {
  id: string; contact_phone: string; contact_name: string | null; lead_id: string | null;
  last_inbound_at: string | null; last_message_at: string | null; handoff_to_human: boolean; opted_out: boolean;
};
export type WAMessage = {
  id: string; conversation_id: string; direction: string; status: string; body: string | null;
  gate_reasons: string[] | null; provider_message_id: string | null; error: string | null; created_at: string;
};

export type Channel = "email" | "whatsapp" | "voice";
export type EmailStep = { template_id: string; delay_hours: number };
export type EmailConfig = {
  account_id: string | null; steps: EmailStep[]; physical_address: string | null;
  website_preview_base_url: string | null; personalize_with_ai: boolean;
};
export type Campaign = {
  id: string; name: string; channel: Channel; status: string; spend_limit: string | null; cost_per_message: string;
  spent: string; send_window: { start_hour: number; end_hour: number } | null; whatsapp_template_id: string | null;
  created_by_user_id: string | null; approved_by_user_id: string | null; approved_at: string | null;
  started_at: string | null; completed_at: string | null; created_at: string;
};
export type CampaignDetail = Campaign & { email: EmailConfig | null; recipient_counts: Record<string, number> };
export type Recipient = {
  id: string; lead_id: string; business_name: string | null; status: string; gate_allowed: boolean | null;
  gate_simulated: boolean | null; gate_reasons: string[] | null; current_step: number; next_due_at: string | null;
  last_sent_at: string | null;
};
export type Approval = { id: string; approver_user_id: string | null; decision: string; note: string | null; created_at: string };
export type CampaignEvent = { id: string; type: string; data: Record<string, unknown> | null; actor_user_id: string | null; created_at: string };

const j = (body: unknown, method = "POST"): RequestInit => ({ method, body: JSON.stringify(body) });
const t = true;

export const email = {
  providers: () => api<ProviderStatus>("/communication/providers", {}, t),
  accounts: () => api<EmailAccount[]>("/email/accounts", {}, t),
  addSmtp: (address: string, display_name?: string) => api<EmailAccount>("/email/accounts", j({ provider: "smtp", address, display_name }), t),
  removeAccount: (id: string) => api<void>(`/email/accounts/${id}`, { method: "DELETE" }, t),
  authorize: (provider: "gmail" | "outlook") => api<{ authorization_url: string }>(`/email/oauth/${provider}/authorize`, {}, t),
  templates: () => api<EmailTemplate[]>("/email/templates", {}, t),
  createTemplate: (b: { name: string; subject: string; html: string; text?: string | null }) => api<EmailTemplate>("/email/templates", j(b), t),
  updateTemplate: (id: string, b: Partial<{ name: string; subject: string; html: string; text: string | null }>) =>
    api<EmailTemplate>(`/email/templates/${id}`, j(b, "PATCH"), t),
  deleteTemplate: (id: string) => api<void>(`/email/templates/${id}`, { method: "DELETE" }, t),
  preview: (b: { subject: string; html: string; text?: string | null; sample?: Record<string, string>; physical_address?: string | null }) =>
    api<Preview>("/email/templates/preview", j(b), t),
  messages: (params: { campaign_id?: string; status?: string; page?: number } = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
    return api<Page<EmailMessage>>(`/email/messages?${q}`, {}, t);
  },
  analytics: (campaign_id?: string) => api<EmailAnalytics>(`/email/analytics${campaign_id ? `?campaign_id=${campaign_id}` : ""}`, {}, t),
};

export const whatsapp = {
  accounts: () => api<WAAccount[]>("/whatsapp/accounts", {}, t),
  addAccount: (phone_number_id: string, display_phone?: string) => api<WAAccount>("/whatsapp/accounts", j({ phone_number_id, display_phone }), t),
  templates: () => api<WATemplate[]>("/whatsapp/templates", {}, t),
  createTemplate: (b: { name: string; language: string; category: string; body: string }) => api<WATemplate>("/whatsapp/templates", j(b), t),
  setTemplateStatus: (id: string, status: string) => api<WATemplate>(`/whatsapp/templates/${id}/status`, j({ status }), t),
  conversations: () => api<Page<Conversation>>("/whatsapp/conversations?page_size=100", {}, t),
  messages: (id: string) => api<WAMessage[]>(`/whatsapp/conversations/${id}/messages`, {}, t),
  send: (id: string, b: { text?: string; template_id?: string; variables?: string[] }) => api<WAMessage>(`/whatsapp/conversations/${id}/messages`, j(b), t),
  patch: (id: string, b: { handoff_to_human?: boolean; lead_id?: string | null }) => api<Conversation>(`/whatsapp/conversations/${id}`, j(b, "PATCH"), t),
};

export const campaigns = {
  list: (page = 1) => api<Page<Campaign>>(`/campaigns?page=${page}`, {}, t),
  get: (id: string) => api<CampaignDetail>(`/campaigns/${id}`, {}, t),
  create: (b: Record<string, unknown>) => api<CampaignDetail>("/campaigns", j(b), t),
  addRecipients: (id: string, b: { lead_ids?: string[]; filter_status?: string[]; filter_city?: string; filter_industry?: string; filter_country?: string }) =>
    api<{ added: number; skipped: number; not_found: number }>(`/campaigns/${id}/recipients`, j(b), t),
  recipients: (id: string) => api<Page<Recipient>>(`/campaigns/${id}/recipients?page_size=200`, {}, t),
  submit: (id: string) => api<CampaignDetail>(`/campaigns/${id}/submit`, { method: "POST" }, t),
  decide: (id: string, decision: "approved" | "rejected", note?: string) => api<CampaignDetail>(`/campaigns/${id}/approval`, j({ decision, note }), t),
  approvals: (id: string) => api<Approval[]>(`/campaigns/${id}/approvals`, {}, t),
  start: (id: string, key: string) =>
    api<{ status: string; dispatched: Record<string, number>; replayed: boolean }>(`/campaigns/${id}/start`, { method: "POST", headers: { "Idempotency-Key": key } }, t),
  tick: (id: string) => api<{ status: string; dispatched: Record<string, number> }>(`/campaigns/${id}/tick`, { method: "POST" }, t),
  pause: (id: string) => api<CampaignDetail>(`/campaigns/${id}/pause`, { method: "POST" }, t),
  cancel: (id: string) => api<CampaignDetail>(`/campaigns/${id}/cancel`, { method: "POST" }, t),
  events: (id: string) => api<Page<CampaignEvent>>(`/campaigns/${id}/events`, {}, t),
};

export const STATUS_TONE: Record<string, string> = {
  draft: "bg-neutral-100 text-neutral-700", pending_approval: "bg-amber-50 text-amber-700", approved: "bg-sky-50 text-sky-700",
  running: "bg-emerald-50 text-emerald-700", paused: "bg-amber-50 text-amber-700", completed: "bg-neutral-100 text-neutral-700",
  cancelled: "bg-neutral-100 text-neutral-500", blocked: "bg-red-50 text-red-700", simulated: "bg-violet-50 text-violet-700",
  sent: "bg-emerald-50 text-emerald-700", delivered: "bg-emerald-50 text-emerald-700", read: "bg-emerald-50 text-emerald-700",
  bounced: "bg-red-50 text-red-700", failed: "bg-red-50 text-red-700", replied: "bg-sky-50 text-sky-700",
  received: "bg-sky-50 text-sky-700", pending: "bg-neutral-100 text-neutral-700", unsubscribed: "bg-neutral-100 text-neutral-500",
  connected: "bg-emerald-50 text-emerald-700", not_configured: "bg-amber-50 text-amber-700", error: "bg-red-50 text-red-700",
  rejected: "bg-red-50 text-red-700",
};

export function newIdempotencyKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}
