import { api, type Page } from "@/lib/api";

export type Plan = { id: string; code: string; name: string; price_monthly: string; currency: string; limits: Record<string, number | null>; trial_days: number; is_public: boolean };
export type Subscription = { id: string; status: string; plan: Plan; current_period_start: string; current_period_end: string; trial_end: string | null; cancel_at_period_end: boolean };
export type UsageItem = { resource: string; used: number; limit: number | null; percent: number | null; level: "ok" | "warning" | "critical" | "exceeded" | "unlimited"; cost: string };
export type Usage = { period: string; items: UsageItem[]; total_cost: string };
export type InvoiceLine = { description: string; quantity: string; unit_amount: string; amount: string };
export type Invoice = { id: string; number: string; status: string; currency: string; subtotal: string; total: string; period_start: string | null; period_end: string | null; due_at: string | null; paid_at: string | null; notes: string | null; created_at: string; lines: InvoiceLine[] };
export type Alert = { id: string; kind: string; resource: string; period: string; threshold: number; value: string; limit_value: string; created_at: string };
export type Budget = { monthly_limit: string | null; alert_thresholds: number[]; hard_stop: boolean; paid_fallback_enabled: boolean; month_spend: string; alerts: Alert[] };
export type Provider = { name: string; status: string; label: string };
export type ChangeResult = { subscription: Subscription; invoice: Invoice | null; proration: Record<string, unknown> };

const T = true;
export const billing = {
  plans: () => api<Plan[]>("/billing/plans", {}, T),
  subscription: () => api<Subscription>("/billing/subscription", {}, T),
  change: (plan_code: string) => api<ChangeResult>("/billing/subscription/change", { method: "POST", body: JSON.stringify({ plan_code }) }, T),
  usage: (period?: string) => api<Usage>(`/billing/usage${period ? `?period=${period}` : ""}`, {}, T),
  budget: () => api<Budget>("/billing/budget", {}, T),
  saveBudget: (b: Omit<Budget, "month_spend" | "alerts">) => api<Budget>("/billing/budget", { method: "PUT", body: JSON.stringify(b) }, T),
  invoices: () => api<Page<Invoice>>("/billing/invoices?page_size=50", {}, T),
  pay: (id: string, provider = "simulated") => api<{ status: string; simulated: boolean; checkout_url?: string | null }>(`/billing/invoices/${id}/pay`, { method: "POST", body: JSON.stringify({ provider }) }, T),
  providers: () => api<Provider[]>("/billing/providers", {}, T),
};

export const LEVEL_COLOR: Record<UsageItem["level"], string> = {
  ok: "#1a7f37", warning: "#b58900", critical: "#e8590c", exceeded: "#d70015", unlimited: "#8e8e93",
};
export const RESOURCE_LABEL: Record<string, string> = {
  users: "Users", leads: "Leads", searches: "Searches", ai_conversations: "AI conversations", voice_minutes: "Voice minutes",
  email_campaigns: "Email campaigns", websites: "Websites", workflows: "Workflows", active_agents: "Active agents", storage_mb: "Storage (MB)",
};
export const money = (v: string | number, cur = "USD") =>
  new Intl.NumberFormat(undefined, { style: "currency", currency: cur }).format(Number(v));
