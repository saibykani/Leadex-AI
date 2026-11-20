// Typed client helpers for the agents + voice modules.
import { api, type Page } from "@/lib/api";

export type Agent = {
  id: string; organization_id: string; name: string; purpose: string | null; industry: string | null;
  personality: string | null; voice: string | null; language: string; speaking_rate: number;
  greeting: string | null; business_info: string | null; qualification_questions: string[] | null;
  conversation_flow: string[] | null; objection_handling: { objection: string; response: string }[] | null;
  tools: string[] | null; escalation_policy: string | null; max_call_seconds: number;
  business_hours: Record<string, unknown> | null; compliance_disclosure: string; status: "draft" | "published" | "killed";
  template_key: string | null; model_config_id: string | null; published_version: number | null;
  created_at: string; updated_at: string;
};
export type AgentInput = Partial<Omit<Agent, "id" | "organization_id" | "status" | "template_key" | "published_version" | "created_at" | "updated_at">>;
export type Template = AgentInput & { key: string; name: string };
export type Tool = { key: string; name: string; description: string; required_permission: string; side_effect: boolean; contacts_person: boolean };
export type Language = { code: string; name: string; status: "enabled" | "evaluation_pending" };
export type Provider = { provider: string; kind: string; status: string; url: string | null; simulated: boolean; models?: string[]; detail?: unknown };
export type Version = { id: string; agent_id: string; version: number; snapshot: Record<string, unknown>; created_at: string };
export type Knowledge = { id: string; agent_id: string; title: string; version: number; chunk_count: number; embedding_status: string; created_at: string };
export type Evaluation = { id: string; kind: string; language: string | null; passed: boolean; score: number | null; notes: string | null; created_at: string };
export type ModelConfig = { id: string; name: string; provider: "ollama" | "simulated"; model: string; temperature: number; max_tokens: number; base_url: string | null };
export type ToolCall = { name: string; arguments: Record<string, unknown>; ok: boolean; result?: Record<string, unknown>; error?: string };
export type Citation = { knowledge_id: string; chunk_id: string; title: string; ordinal: number; score: number; text: string };
export type TestResult = {
  run_id: string; status: "ok" | "error" | "not_configured"; reply: string; simulated: boolean; provider: string;
  model: string | null; latency_ms: number; tool_calls: ToolCall[]; citations: Citation[]; retrieval_mode: string;
  error: string | null; steps: { step: string; latency_ms: number; data: unknown }[];
};
export type Call = {
  id: string; lead_id: string; agent_id: string; agent_version: number | null; direction: string; status: string;
  gate_reasons: string[] | null; provider: string; language: string; simulated: boolean; started_at: string | null;
  ended_at: string | null; duration_s: number | null; created_at: string;
};
export type CallDetail = Call & {
  events: { id: string; type: string; data: Record<string, unknown> | null; created_at: string }[];
  transcript: { seq: number; speaker: string; text: string; simulated: boolean; created_at: string }[];
  summary: { summary: string; simulated: boolean } | null;
  disposition: { disposition: string; notes: string | null } | null;
  recording: { enabled: boolean; consent_reference: string | null } | null;
};

const j = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

export const agentsApi = {
  list: () => api<Page<Agent>>("/agents?page_size=100", {}, true),
  get: (id: string) => api<Agent>(`/agents/${id}`, {}, true),
  create: (b: AgentInput & { name: string; compliance_disclosure: string }) => api<Agent>("/agents", j("POST", b), true),
  update: (id: string, b: AgentInput) => api<Agent>(`/agents/${id}`, j("PATCH", b), true),
  remove: (id: string) => api<void>(`/agents/${id}`, j("DELETE"), true),
  fromTemplate: (template_key: string, business_name?: string) =>
    api<Agent>("/agents/from-template", j("POST", { template_key, business_name: business_name || undefined }), true),
  templates: () => api<{ items: Template[] }>("/agents/templates", {}, true).then((r) => r.items),
  tools: () => api<{ items: Tool[] }>("/agents/tools", {}, true).then((r) => r.items),
  languages: () => api<{ items: Language[] }>("/agents/languages", {}, true).then((r) => r.items),
  providers: () => api<{ providers: Provider[] }>("/ai/providers", {}, true).then((r) => r.providers),
  modelConfigs: () => api<ModelConfig[]>("/ai/model-configs", {}, true),
  publish: (id: string) => api<Version>(`/agents/${id}/publish`, j("POST"), true),
  kill: (id: string) => api<Agent>(`/agents/${id}/kill`, j("POST"), true),
  reactivate: (id: string) => api<Agent>(`/agents/${id}/reactivate`, j("POST"), true),
  versions: (id: string) => api<Version[]>(`/agents/${id}/versions`, {}, true),
  knowledge: (id: string) => api<Knowledge[]>(`/agents/${id}/knowledge`, {}, true),
  addKnowledge: (id: string, title: string, content: string) => api<Knowledge>(`/agents/${id}/knowledge`, j("POST", { title, content }), true),
  deleteKnowledge: (id: string, kid: string) => api<void>(`/agents/${id}/knowledge/${kid}`, j("DELETE"), true),
  evaluations: (id: string) => api<Evaluation[]>(`/agents/${id}/evaluations`, {}, true),
  test: (id: string, body: { messages: { role: "user" | "assistant"; content: string }[]; provider?: "ollama" | "simulated"; use_knowledge?: boolean; invoke_tools?: { name: string; arguments: Record<string, unknown> }[]; dry_run?: boolean }) =>
    api<TestResult>(`/agents/${id}/test`, j("POST", body), true),
};

export const callsApi = {
  list: (params = "") => api<Page<Call>>(`/calls?page_size=100${params}`, {}, true),
  get: (id: string) => api<CallDetail>(`/calls/${id}`, {}, true),
  /** Idempotency-Key is mandatory server-side; a fresh key per user action. Blocked calls throw ApiError(422, "call_blocked"). */
  create: (lead_id: string, agent_id: string, key = crypto.randomUUID()) =>
    api<Call>("/calls", { method: "POST", body: JSON.stringify({ lead_id, agent_id }), headers: { "Idempotency-Key": key } }, true),
};

export const REASON_LABELS: Record<string, string> = {
  agent_not_published: "Agent is not published",
  agent_killed: "Agent kill switch is on",
  global_kill_switch: "Global voice kill switch is on",
  no_consent_reference: "Lead has no consent reference",
  jurisdiction_unknown: "Lead country unknown",
  lead_not_found: "Lead not found",
  outside_calling_window: "Outside the permitted calling window",
  telephony_not_configured: "No telephony provider configured",
  telephony_needs_public_url: "Telephony needs a public webhook URL (set PUBLIC_WEBHOOK_BASE_URL)",
  invalid_phone_number: "The lead's phone number is not a valid international number",
};
export function reasonLabel(r: string): string {
  if (REASON_LABELS[r]) return REASON_LABELS[r];
  const [k, v] = r.split(":");
  if (k === "language_evaluation_pending") return `Language "${v}" has no passed evaluation yet`;
  if (k === "lead_status_not_eligible") return `Lead status "${v}" is not eligible`;
  if (k === "no_consent_record") return `No ${v} consent record`;
  return r;
}

export const STATUS_STYLES: Record<string, string> = {
  draft: "bg-neutral-100 text-neutral-700",
  published: "bg-green-100 text-green-800",
  killed: "bg-red-100 text-red-700",
  blocked: "bg-red-100 text-red-700",
  simulated_completed: "bg-amber-100 text-amber-800",
  not_configured: "bg-neutral-100 text-neutral-700",
  completed: "bg-green-100 text-green-800",
  queued: "bg-blue-100 text-blue-800",
};

export const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);
