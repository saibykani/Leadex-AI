// Typed client for insights / copilot / onboarding / demo endpoints (apps/api/app/modules/{insights,copilot,demo}).
import { api } from "@/lib/api";

export type SeriesKey = "leads" | "conversions" | "outcomes_with_budget" | "websites" | "agent_runs" | "calls";
export type OverviewPoint = { date: string } & Record<SeriesKey, number>;
export type Overview = {
  days: number; start: string; end: string; points: OverviewPoint[]; totals: Record<SeriesKey, number>;
  previous: { leads: number };
  revenue: { kind: "invoices_paid" | "commissions_settled"; currency: string; total: number; points: { date: string; value: number }[] }[];
  notes: { revenue: string };
};
export type Money = Record<string, number>;
export type PipelineValue = {
  stages: { stage: string; leads: number; with_budget: number; value: Money }[];
  open_value: Money; leads_without_budget: number; method: string;
};
export type Forecast = {
  status: "ok" | "insufficient_data"; formula: string; closed_deals: number; won: number; lost: number;
  min_closed_required: number; win_rate: number | null; message: string | null; forecast: Money;
  stages: { stage: string; rate: number; sample: number; rate_source: "stage" | "overall"; value: Money; weighted: Money }[];
};
export type Facts = {
  total_leads: number; by_status: Record<string, number>; new_leads_24h: number; new_leads_7d: number; hot_leads: number;
  overdue_tasks: number; open_tasks: number; campaigns_running: number; websites_published: number; websites_total: number;
  businesses: number; agents: number; referrals: number; converted: number; pipeline_open_value: Money; leads_without_budget: number;
};
export type Briefing = { text: string; lines: string[]; mode: "deterministic" | "ollama"; model: string | null; facts: Facts; generated_at: string };
export type Analytics = {
  cohorts: { week: string; created: number; engaged: number; converted: number }[];
  by_industry: { key: string; leads: number; converted: number; rate: number }[];
  by_city: { key: string; leads: number; converted: number; rate: number }[];
  interest: Record<string, number>;
  budget_histogram: { from: number; to: number | null; count: number; currency: string }[];
  agents: { agent_id: string; name: string; runs: number; errors: number; avg_latency_ms: number | null; outcomes: Record<string, number> }[];
  funnel: { stage: string; count: number }[];
};
export type Opportunity = {
  lead_id: string; business_name: string; status: string; city: string | null; interest: string; budget_mid: number; currency: string;
  budget_min: number | null; budget_max: number | null; timeline: string | null; next_step: string | null;
};
export type CopilotRow = { type: string; id: string; label: string; href?: string; [k: string]: unknown };
export type CopilotAnswer = {
  answer: string; tool: string | null; args: Record<string, unknown>; rows: CopilotRow[]; citations: { label: string; href: string }[];
  refused: boolean; mode: string; model: string | null; read_only: boolean;
};
export type OnboardingStep = { key: string; title: string; done: boolean; skipped: boolean; source: "data" | "manual" | null; evidence: string | null };
export type Onboarding = {
  steps: OnboardingStep[]; completed: number; total: number; percent: number; profile: Record<string, string>;
  organization: { name: string | null; country_code: string | null };
};
export type DemoInfo = { exists: boolean; organization_id: string | null; summary: { counts?: Record<string, number> } | null; created_at?: string; name?: string };

export const growth = {
  overview: (days = 30) => api<Overview>(`/insights/overview?days=${days}`, {}, true),
  pipelineValue: () => api<PipelineValue>("/insights/pipeline-value", {}, true),
  forecast: () => api<Forecast>("/insights/forecast", {}, true),
  briefing: (polish = false) => api<Briefing>(`/insights/briefing${polish ? "?polish=true" : ""}`, {}, true),
  analytics: (weeks = 8) => api<Analytics>(`/insights/analytics?weeks=${weeks}`, {}, true),
  opportunities: (limit = 6) => api<Opportunity[]>(`/insights/opportunities?limit=${limit}`, {}, true),
  ask: (question: string) => api<CopilotAnswer>("/copilot/ask", { method: "POST", body: JSON.stringify({ question }) }, true),
  suggestions: () => api<{ suggestions: string[] }>("/copilot/suggestions", {}, true),
  onboarding: () => api<Onboarding>("/onboarding", {}, true),
  onboardingStep: (step: string, action: "complete" | "skip" | "reset" = "complete", profile?: Record<string, string>) =>
    api<Onboarding>("/onboarding/step", { method: "POST", body: JSON.stringify({ step, action, profile }) }, true),
  demo: () => api<DemoInfo>("/demo"),
  demoCurrent: () => api<{ is_demo: boolean }>("/demo/current", {}, true),
  createDemo: () => api<DemoInfo>("/demo", { method: "POST" }),
  resetDemo: () => api<DemoInfo>("/demo/reset", { method: "POST" }),
  deleteDemo: () => api<void>("/demo", { method: "DELETE" }),
};

export function fmtMoney(v: number, currency: string) {
  try { return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0, notation: v >= 1e6 ? "compact" : "standard" }).format(v); }
  catch { return `${currency} ${Math.round(v).toLocaleString()}`; }
}
export const money = (m: Money) => Object.entries(m).map(([c, v]) => fmtMoney(v, c));
