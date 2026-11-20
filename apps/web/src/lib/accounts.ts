// Account lifecycle client: password reset, email verification, invitations, sessions.
import { api } from "@/lib/api";

export type Delivery = { status: string; simulated: boolean; dev_link: string | null };
export type Invite = { id: string; email: string; role: string; expires_at: string; created_at: string };
export type InvitePreview = { email: string; organization_name: string; role: string; account_exists: boolean };
export type DeviceSession = { id: string; user_agent: string | null; ip_address: string | null; created_at: string; expires_at: string };

function post<T>(path: string, body?: unknown) {
  return api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
}

export const accounts = {
  forgot: (email: string) => post<Delivery>("/auth/password/forgot", { email }),
  reset: (token: string, password: string) => post<void>("/auth/password/reset", { token, password }),
  requestVerify: () => post<Delivery>("/auth/email/verify/request"),
  verify: (token: string) => post<void>("/auth/email/verify", { token }),
  previewInvite: (token: string) => post<InvitePreview>("/auth/invites/preview", { token }),
  acceptInvite: (token: string, full_name?: string, password?: string) => post<void>("/auth/invites/accept", { token, full_name, password }),
  invites: (org: string) => api<Invite[]>(`/organizations/${org}/invitations`),
  invite: (org: string, email: string, role: string) => post<Delivery & { invite: Invite }>(`/organizations/${org}/invitations`, { email, role }),
  revokeInvite: (org: string, id: string) => api<void>(`/organizations/${org}/invitations/${id}`, { method: "DELETE" }),
  sessions: () => api<DeviceSession[]>("/auth/sessions"),
  revokeSession: (id: string) => api<void>(`/auth/sessions/${id}`, { method: "DELETE" }),
  revokeOthers: () => post<{ revoked: number }>("/auth/sessions/revoke-others", {}), // current session kept via cookie
};

export const tokenFromUrl = () => (typeof window === "undefined" ? "" : new URLSearchParams(window.location.search).get("token") ?? "");

/** Short device description from a user-agent string. */
export function deviceLabel(ua: string | null): string {
  if (!ua) return "Unknown device";
  const b = /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox"
    : /Safari\//.test(ua) ? "Safari" : /python|curl|httpx|testclient/i.test(ua) ? "Script / API client" : "Browser";
  const os = /Windows/.test(ua) ? "Windows" : /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iOS"
    : /Mac OS/.test(ua) ? "macOS" : /Linux/.test(ua) ? "Linux" : "";
  return os ? `${b} on ${os}` : b;
}
