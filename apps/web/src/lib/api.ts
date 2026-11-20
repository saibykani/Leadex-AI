// Typed API client.
// Auth: the refresh token lives only in an httpOnly cookie set by the API (JavaScript cannot read it, so XSS cannot
// steal it). The short-lived access token is kept in memory only; after a reload it is re-obtained via /auth/refresh.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Organization = {
  id: string; name: string; slug: string; country_code: string | null;
  is_platform_owner: boolean; status: string; created_at: string;
};
export type Membership = { organization: Organization; role: string; permissions: string[] };
export type Me = { user: { id: string; email: string; full_name: string; is_superadmin: boolean; mfa_enabled: boolean; email_verified_at?: string | null }; memberships: Membership[] };
export type Member = { id: string; user_id: string; email: string; full_name: string; role: string; status: string };
export type AuditLog = { id: string; action: string; entity_type: string | null; entity_id: string | null; actor_user_id: string | null; created_at: string };
export type Page<T> = { items: T[]; total: number; page: number; page_size: number };
type Tokens = { access_token: string; refresh_token: string };

export const BILLING_EVENT = "leadex:billing-required";
export const isBillingError = (e: unknown): e is ApiError => e instanceof ApiError && e.status === 402;

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) { super(message); }
}

let accessToken: string | null = null;
if (typeof window !== "undefined") {
  // One-time cleanup of tokens stored by older versions of the app.
  try { localStorage.removeItem("lx_access"); localStorage.removeItem("lx_refresh"); } catch { /* storage unavailable */ }
}

const store = {
  get access() { return accessToken; },
  get org() { if (typeof window === "undefined") return null; try { return localStorage.getItem("lx_org"); } catch { return null; } },
  save(t: { access_token: string }) { accessToken = t.access_token; },
  setOrg(id: string) { try { localStorage.setItem("lx_org", id); } catch { /* ignore */ } },
  clear() { accessToken = null; try { localStorage.removeItem("lx_org"); } catch { /* ignore */ } },
};
export const session = store;

async function raw(path: string, init: RequestInit = {}, tenant = false): Promise<Response> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json"); // browsers set the multipart boundary themselves
  headers.set("X-Requested-With", "leadex"); // required by the API before it accepts the refresh cookie
  if (store.access) headers.set("Authorization", `Bearer ${store.access}`);
  if (tenant && store.org) headers.set("X-Organization-Id", store.org);
  return fetch(`${API_URL}/api/v1${path}`, { ...init, headers, credentials: "include" });
}

let refreshing: Promise<boolean> | null = null;
async function tryRefresh(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      const r = await fetch(`${API_URL}/api/v1/auth/refresh`, {
        method: "POST", credentials: "include", headers: { "X-Requested-With": "leadex" },
      });
      if (!r.ok) return false;
      store.save(await r.json());
      return true;
    } catch { return false; }
  })().finally(() => { refreshing = null; });
  return refreshing;
}

/** True when signed in: uses the in-memory token or silently renews it from the httpOnly cookie. */
export async function ensureSession(): Promise<boolean> {
  return !!store.access || tryRefresh();
}

export async function api<T>(path: string, init: RequestInit = {}, tenant = false): Promise<T> {
  let r = await raw(path, init, tenant);
  if (r.status === 401 && !path.startsWith("/auth/login") && (await tryRefresh())) r = await raw(path, init, tenant);
  if (r.status === 204) return undefined as T;
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const e = body?.error ?? {};
    const detail = Array.isArray(e.details) && e.details[0]?.msg ? `: ${e.details[0].msg}` : "";
    const err = new ApiError(r.status, e.code ?? "error", (e.message ?? "Request failed") + detail, e.details);
    // Plan limit / inactive subscription / budget hard stop: the app shell shows a notice linking to /billing.
    if (r.status === 402 && typeof window !== "undefined") window.dispatchEvent(new CustomEvent(BILLING_EVENT, { detail: err }));
    throw err;
  }
  return body as T;
}

export const auth = {
  async login(email: string, password: string) {
    store.save(await api<Tokens>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }));
  },
  async register(data: { email: string; password: string; full_name: string; organization_name: string; country_code?: string }) {
    store.save(await api<Tokens>("/auth/register", { method: "POST", body: JSON.stringify(data) }));
  },
  async logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    store.clear();
  },
  me: () => api<Me>("/auth/me"),
};
