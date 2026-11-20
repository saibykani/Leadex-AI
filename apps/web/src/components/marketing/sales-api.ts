import { API_URL } from "@/lib/api";

export type PublicPlan = {
  code: string; name: string; trial_days: number;
  price_monthly: string | null; price_annual: string | null; currency: string;
  contact_sales: boolean; highlight: boolean; badge: string | null; tagline: string | null;
  bullets: string[]; limits: Record<string, number | null>; features: string[];
};
export type Slot = { start: string; end: string; label: string };
export type SlotDay = { date: string; timezone: string; slot_minutes: number; booking_enabled: boolean; weekdays: number[]; horizon_days: number; slots: Slot[] };
export type SubmitResult = { reference: string; duplicate: boolean; ics_url: string | null; slot_start: string | null };

export class PublicError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers: { "Content-Type": "application/json" } });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const e = body?.error ?? {};
    throw new PublicError(r.status, e.code ?? "error", r.status === 429 ? "Too many attempts. Please wait a minute and try again." : (e.message ?? "Something went wrong"));
  }
  return body as T;
}

export const salesApi = {
  pricing: () => call<{ plans: PublicPlan[] }>("/public/pricing"),
  slots: (date: string) => call<SlotDay>(`/public/sales/slots?date=${date}`),
  contact: (b: object) => call<SubmitResult>("/public/sales/contact", { method: "POST", body: JSON.stringify(b) }),
  book: (b: object) => call<SubmitResult>("/public/sales/book", { method: "POST", body: JSON.stringify(b) }),
  icsHref: (path: string) => `${API_URL}${path}`,
};

export const LIMIT_LABEL: Record<string, string> = {
  users: "Team members", leads: "Leads in CRM", searches: "Discovery searches / mo", ai_tokens: "AI actions / mo",
  voice_minutes: "Voice minutes / mo", email_accounts: "Email inboxes", websites: "Websites", workflows: "Workflows",
  agents: "AI agents", storage_mb: "Storage",
};

export function fmtLimit(k: string, v: number | null | undefined): string {
  if (v === null || v === undefined) return "Unlimited";
  if (k === "storage_mb") return v >= 1000 ? `${(v / 1000).toLocaleString()} GB` : `${v} MB`;
  return v.toLocaleString();
}

export function money(v: string | number, currency: string) {
  const n = typeof v === "string" ? Number(v) : v;
  try { return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: n % 1 ? 2 : 0 }).format(n); }
  catch { return `${currency} ${n}`; }
}
