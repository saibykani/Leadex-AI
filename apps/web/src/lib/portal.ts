// Marketplace portal client (external providers and customers). Completely separate from the staff session:
// the short-lived portal token is kept in sessionStorage only and sent as a Bearer token to /marketplace-portal.
import { api, API_URL, ApiError } from "@/lib/api";

const KEY = "lx_portal";
export type Delivery = { status: string; simulated: boolean; dev_link: string | null; dev_links: string[] };
export type Invite = Delivery & { account_id: string; role: string; email: string };
export type PortalSession = { portal_token: string; role: "provider" | "customer"; expires_in: number; organization_name: string | null };
export type PortalMe = { role: "provider" | "customer"; email: string; subject_id: string; organization_id: string };
export type Money = { currency: string; accrued: string; reversed: string; invoiced: string; paid: string; refunded: string; settled: string; outstanding: string };
export type ProviderRef = {
  id: string; status: string; provider_name: string | null; requirement_title: string | null; updated_at: string;
  requirement: { title: string; city: string | null; country: string | null; budget_min: string | null; budget_max: string | null; currency: string; timeline: string | null; description: string | null };
  customer: { full_name: string; email: string; phone: string | null } | null;
};
export type CustomerReq = {
  id: string; title: string; city: string | null; country: string | null; status: string; timeline: string | null;
  description: string | null; contact_permission: boolean; currency: string; budget_min: string | null; budget_max: string | null;
  referrals: { id: string; provider_name: string | null; status: string; updated_at: string }[];
};

export const portalToken = {
  get(): string | null { try { return sessionStorage.getItem(KEY); } catch { return null; } },
  set(t: string) { try { sessionStorage.setItem(KEY, t); } catch { /* storage unavailable */ } },
  clear() { try { sessionStorage.removeItem(KEY); } catch { /* ignore */ } },
};

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const t = portalToken.get();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  const r = await fetch(`${API_URL}/api/v1/marketplace-portal${path}`, { ...init, headers });
  const body = r.status === 204 ? undefined : await r.json().catch(() => ({}));
  if (!r.ok) {
    const e = (body as { error?: { code?: string; message?: string } })?.error ?? {};
    if (r.status === 401) portalToken.clear();
    throw new ApiError(r.status, e.code ?? "error", e.message ?? "Request failed");
  }
  return body as T;
}
const post = <T,>(p: string, b?: unknown) => call<T>(p, { method: "POST", body: b === undefined ? undefined : JSON.stringify(b) });

export const portal = {
  login: (email: string) => post<Delivery>("/login", { email }),
  exchange: (token: string) => post<PortalSession>("/exchange", { token }),
  me: () => call<PortalMe>("/me"),
  provider: {
    referrals: () => call<ProviderRef[]>("/provider/referrals"),
    accept: (id: string) => post<ProviderRef>(`/provider/referrals/${id}/accept`),
    decline: (id: string) => post<ProviderRef>(`/provider/referrals/${id}/decline`),
    commissions: () => call<{ totals: Money[]; referrals: { referral_id: string; requirement_title: string | null; referral_status: string; balances: Money[] }[] }>("/provider/commissions"),
  },
  customer: {
    requirements: () => call<CustomerReq[]>("/customer/requirements"),
    withdraw: (id: string) => post<CustomerReq>(`/customer/requirements/${id}/withdraw-contact`),
  },
};

// Staff side (uses the normal staff session).
export const portalInvite = {
  provider: (id: string) => api<Invite>(`/marketplace/providers/${id}/portal-invite`, { method: "POST" }, true),
  requirement: (id: string) => api<Invite>(`/marketplace/requirements/${id}/portal-invite`, { method: "POST" }, true),
};
