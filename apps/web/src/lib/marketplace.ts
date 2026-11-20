// Marketplace API helpers (requirements, providers, matching, referrals, commissions, portals).
import { api, API_URL, ApiError, session, type Page } from "@/lib/api";

export type Category = { id: string; slug: string; name: string; is_system: boolean };
export type Requirement = {
  id: string; customer_id: string; category_id: string; title: string; city: string | null; country: string | null;
  budget_min: string | null; budget_max: string | null; currency: string; timeline: string | null;
  description: string | null; preferences: Record<string, unknown> | null; contact_permission: boolean;
  consent_reference: string | null; status: string; created_at: string;
};
export type Provider = {
  id: string; business_name: string; legal_name: string | null; email: string | null; phone: string | null;
  website: string | null; description: string | null; service_areas: { city?: string; country?: string }[] | null;
  experience_years: number | null; portfolio: unknown[] | null; credentials: unknown[] | null;
  verification_status: "unverified" | "pending" | "verified" | "rejected"; availability: string;
  price_min: string | null; price_max: string | null; currency: string; pricing_notes: string | null;
  portal_user_id: string | null; category_ids: string[]; created_at: string;
};
export type Factor = { score: number; reason: string; weight: number };
export type Match = {
  id: string; requirement_id: string; provider_id: string; provider_name: string | null; score: number;
  explanation: { factors: Record<string, Factor>; unverified_flag: boolean; penalty: string | null };
  created_at: string;
};
export type Doc = { id: string; document_type: string; filename: string; content_type: string; size_bytes: number; sha256: string; created_at: string };
export type Verification = { id: string; method: string; registry_name: string | null; reference: string | null; decision: string; evidence: string | null; created_at: string };
export type Referral = {
  id: string; requirement_id: string; provider_id: string; status: string; deal_value: string | null;
  currency: string; created_at: string; updated_at: string; provider_name: string | null; requirement_title: string | null;
};
export type RefEvent = { id: string; type: string; from_status: string | null; to_status: string | null; note: string | null; created_at: string };
export type Agreement = {
  id: string; provider_id: string; type: "fixed" | "percentage" | "negotiated"; value: string | null; currency: string;
  splits: { party: string; pct: string }[] | null; settlement_conditions: Record<string, boolean> | null; active: boolean;
  notes: string | null; created_at: string;
};
export type Tx = { id: string; referral_id: string; kind: string; amount: string; currency: string; reference: string | null; data: Record<string, unknown> | null; created_at: string };
export type Balance = { currency: string; accrued: string; reversed: string; invoiced: string; paid: string; refunded: string; settled: string; outstanding: string };
export type Dispute = { id: string; referral_id: string; reason: string; amount: string | null; status: string; resolution: string | null; created_at: string };
export type ReferralCommission = { referral_id: string; balances: Balance[]; transactions: Tx[]; disputes: Dispute[]; settleable: boolean; blockers: string[] };
export type PortalReferral = Referral & {
  requirement: { title: string; city: string | null; country: string | null; budget_min: string | null; budget_max: string | null; currency: string; timeline: string | null; description: string | null };
  customer: { full_name: string; email: string; phone: string | null } | null;
};

export const REFERRAL_STATUSES = ["requirement_received", "matched", "invited", "accepted", "introduced", "meeting",
  "quotation", "negotiation", "converted", "declined", "lost"] as const;
export const NEXT: Record<string, string[]> = {
  requirement_received: ["matched", "declined", "lost"], matched: ["invited", "declined", "lost"],
  invited: ["accepted", "declined", "lost"], accepted: ["introduced", "lost"], introduced: ["meeting", "quotation", "lost"],
  meeting: ["quotation", "lost"], quotation: ["negotiation", "converted", "lost"], negotiation: ["quotation", "converted", "lost"],
  converted: [], declined: [], lost: [],
};
export const PROVIDER_ALLOWED = new Set(["accepted", "declined", "meeting", "quotation", "negotiation", "converted", "lost"]);
export const label = (s: string) => s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

const t = <T,>(path: string, init: RequestInit = {}) => api<T>(path, init, true);
const post = <T,>(path: string, body?: unknown, headers?: HeadersInit) =>
  t<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body), headers });

export const mkt = {
  categories: () => t<Category[]>("/marketplace/categories"),
  requirements: () => t<Page<Requirement>>("/marketplace/requirements?page_size=100"),
  createRequirement: (b: unknown) => post<Requirement>("/marketplace/requirements", b),
  match: (id: string) => post<Match[]>(`/marketplace/requirements/${id}/match`),
  matches: (id: string) => t<Match[]>(`/marketplace/requirements/${id}/matches`),
  providers: () => t<Page<Provider>>("/marketplace/providers?page_size=200"),
  provider: (id: string) => t<Provider>(`/marketplace/providers/${id}`),
  createProvider: (b: unknown) => post<Provider>("/marketplace/providers", b),
  updateProvider: (id: string, b: unknown) => t<Provider>(`/marketplace/providers/${id}`, { method: "PATCH", body: JSON.stringify(b) }),
  documents: (id: string) => t<Doc[]>(`/marketplace/providers/${id}/documents`),
  verifications: (id: string) => t<Verification[]>(`/marketplace/providers/${id}/verifications`),
  verify: (id: string, b: unknown) => post<Verification>(`/marketplace/providers/${id}/verify`, b),
  async upload(id: string, documentType: string, file: File): Promise<Doc> {
    // multipart: bypasses api() because it forces a JSON content type
    const fd = new FormData();
    fd.set("document_type", documentType);
    fd.set("file", file);
    const r = await fetch(`${API_URL}/api/v1/marketplace/providers/${id}/documents`, {
      method: "POST", body: fd,
      headers: { Authorization: `Bearer ${session.access ?? ""}`, "X-Organization-Id": session.org ?? "" },
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new ApiError(r.status, body?.error?.code ?? "error", body?.error?.message ?? "Upload failed");
    return body as Doc;
  },
  referrals: () => t<Page<Referral>>("/referrals?page_size=500"),
  referral: (id: string) => t<Referral>(`/referrals/${id}`),
  events: (id: string) => t<RefEvent[]>(`/referrals/${id}/events`),
  createReferral: (requirement_id: string, provider_id: string) =>
    post<Referral>("/referrals", { requirement_id, provider_id }, { "Idempotency-Key": `${requirement_id}:${provider_id}` }),
  setStatus: (id: string, status: string, extra: Record<string, unknown> = {}) => post<Referral>(`/referrals/${id}/status`, { status, ...extra }),
  agreements: () => t<Agreement[]>("/commissions/agreements"),
  createAgreement: (b: unknown) => post<Agreement>("/commissions/agreements", b),
  deactivateAgreement: (id: string) => t<void>(`/commissions/agreements/${id}`, { method: "DELETE" }),
  summary: () => t<{ balances: Balance[]; open_disputes: number; transactions: Tx[] }>("/commissions"),
  disputes: () => t<Dispute[]>("/commissions/disputes"),
  commission: (rid: string) => t<ReferralCommission>(`/referrals/${rid}/commission`),
  ledger: (rid: string, action: "accrue" | "invoice" | "payment" | "refund" | "settle", b: unknown = {}) =>
    post<Tx>(`/referrals/${rid}/commission/${action}`, action === "settle" ? undefined : b),
  dispute: (rid: string, reason: string, amount?: string) => post<Dispute>(`/referrals/${rid}/commission/disputes`, { reason, amount: amount || undefined }),
  resolveDispute: (id: string, b: unknown) => post<Dispute>(`/commissions/disputes/${id}/resolve`, b),
  portalProvider: {
    referrals: () => t<PortalReferral[]>("/portal/provider/referrals"),
    profile: () => t<Provider[]>("/portal/provider/profile"),
    earnings: () => t<Balance[]>("/portal/provider/earnings"),
    accept: (id: string) => post<PortalReferral>(`/portal/provider/referrals/${id}/accept`),
    decline: (id: string) => post<PortalReferral>(`/portal/provider/referrals/${id}/decline`),
    status: (id: string, status: string, deal_value?: string) => post<PortalReferral>(`/portal/provider/referrals/${id}/status`, { status, deal_value: deal_value || undefined }),
  },
  portalCustomer: {
    requirements: () => t<Requirement[]>("/portal/customer/requirements"),
    requirement: (id: string) => t<{
      requirement: Requirement;
      matches: { provider_name: string | null; score: number; unverified: boolean; factors: Record<string, string> }[];
      referrals: { id: string; status: string; updated_at: string; provider_name: string | null }[];
    }>(`/portal/customer/requirements/${id}`),
  },
};

export const fmtMoney = (v: string | null | undefined, cur: string) =>
  v == null ? "—" : `${cur} ${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
