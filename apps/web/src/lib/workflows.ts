import { api, type Page } from "@/lib/api";

export type WfNode = { id: string; type: string; config: Record<string, unknown>; position?: { x: number; y: number } };
export type WfEdge = { source: string; target: string; label?: string };
export type Graph = { nodes: WfNode[]; edges: WfEdge[] };
export type Workflow = {
  id: string; name: string; description: string | null; status: string; trigger_type: string | null;
  draft_graph: Graph | null; current_version_id: string | null; created_at: string; updated_at: string;
  webhook_secret?: string | null;
};
export type Version = { id: string; workflow_id: string; version: number; graph: Graph; created_at: string };
export type Execution = {
  id: string; workflow_id: string; version_id: string; status: string; trigger_type: string;
  trigger_payload: Record<string, unknown> | null; idempotency_key: string; resume_at: string | null;
  error: string | null; created_at: string; finished_at: string | null;
};
export type ExecEvent = {
  id: string; seq: number; node_key: string | null; node_type: string | null; event: string; attempt: number;
  output: Record<string, unknown> | null; error: string | null; created_at: string;
};
export type Approval = { id: string; execution_id: string; node_key: string; status: string; message: string | null };
export type Analytics = { total: number; by_status: Record<string, number>; success_rate: number | null; failed_nodes: Record<string, number> };

export const NODE_TYPES: { type: string; label: string; group: string; defaults: Record<string, unknown> }[] = [
  { type: "trigger", label: "Trigger", group: "Start", defaults: { trigger_type: "manual" } },
  { type: "condition", label: "Condition", group: "Logic", defaults: { field: "payload.score", op: "gte", value: 50 } },
  { type: "filter", label: "Filter", group: "Logic", defaults: { field: "lead.status", op: "eq", value: "verified" } },
  { type: "delay", label: "Delay", group: "Logic", defaults: { seconds: 3600 } },
  { type: "approval", label: "Approval", group: "Logic", defaults: { message: "Please review" } },
  { type: "ai_action", label: "AI action", group: "Actions", defaults: { prompt: "Summarize this lead" } },
  { type: "crm_update", label: "CRM update", group: "Actions", defaults: { score: 50 } },
  { type: "lead_assignment", label: "Assign lead", group: "Actions", defaults: {} },
  { type: "notification", label: "Notification", group: "Actions", defaults: { message: "" } },
  { type: "api_request", label: "API request", group: "Integrations", defaults: { url: "https://", method: "GET", retries: 2, timeout_seconds: 10 } },
  { type: "webhook_out", label: "Webhook out", group: "Integrations", defaults: { url: "https://", retries: 2 } },
  { type: "email", label: "Email (gated)", group: "Outreach", defaults: { template: "" } },
  { type: "whatsapp", label: "WhatsApp (gated)", group: "Outreach", defaults: { template: "" } },
  { type: "voice_call", label: "Voice call (gated)", group: "Outreach", defaults: {} },
];
export const TRIGGERS = ["manual", "lead_created", "business_discovered", "webhook", "schedule"];
export const BRANCH_LABELS: Record<string, string[]> = {
  condition: ["true", "false"], approval: ["approved", "rejected"],
  email: ["blocked", "simulated", "queued"], whatsapp: ["blocked", "simulated", "queued"], voice_call: ["blocked", "simulated", "queued"],
};

const T = true;
export const workflows = {
  list: () => api<Page<Workflow>>("/workflows?page_size=100", {}, T),
  get: (id: string) => api<Workflow>(`/workflows/${id}`, {}, T),
  create: (name: string, graph?: Graph) => api<Workflow>("/workflows", { method: "POST", body: JSON.stringify({ name, graph }) }, T),
  update: (id: string, body: Partial<{ name: string; description: string; graph: Graph; status: string }>) =>
    api<Workflow>(`/workflows/${id}`, { method: "PATCH", body: JSON.stringify(body) }, T),
  remove: (id: string) => api<void>(`/workflows/${id}`, { method: "DELETE" }, T),
  validate: (graph: Graph) => api<{ valid: boolean; errors: string[] }>("/workflows/validate", { method: "POST", body: JSON.stringify(graph) }, T),
  publish: (id: string, graph: Graph) => api<Version>(`/workflows/${id}/versions`, { method: "POST", body: JSON.stringify(graph) }, T),
  versions: (id: string) => api<Version[]>(`/workflows/${id}/versions`, {}, T),
  execute: (id: string, payload: Record<string, unknown>, key?: string) =>
    api<Execution>(`/workflows/${id}/execute`, { method: "POST", body: JSON.stringify({ payload }), headers: key ? { "Idempotency-Key": key } : {} }, T),
  executions: (id: string) => api<Page<Execution>>(`/workflows/${id}/executions?page_size=20`, {}, T),
  events: (execId: string) => api<ExecEvent[]>(`/workflows/executions/${execId}/events`, {}, T),
  resume: (execId: string) => api<Execution>(`/workflows/executions/${execId}/resume`, { method: "POST" }, T),
  approvals: () => api<Approval[]>("/workflows/approvals", {}, T),
  decide: (approvalId: string, approve: boolean) =>
    api<Execution>(`/workflows/approvals/${approvalId}/${approve ? "approve" : "reject"}`, { method: "POST", body: "{}" }, T),
  analytics: (id?: string) => api<Analytics>(id ? `/workflows/${id}/analytics` : "/workflows/analytics", {}, T),
  rotateSecret: (id: string) => api<Workflow>(`/workflows/${id}/webhook-secret`, { method: "POST" }, T),
  settings: () => api<{ allowed_hosts: string[] }>("/workflows/settings", {}, T),
  saveSettings: (allowed_hosts: string[]) => api<{ allowed_hosts: string[] }>("/workflows/settings", { method: "PUT", body: JSON.stringify({ allowed_hosts }) }, T),
};

export const STATUS_COLOR: Record<string, string> = {
  succeeded: "#1a7f37", failed: "#d70015", retried: "#b25000", started: "#0071e3", skipped: "#8e8e93",
  waiting_approval: "#8944ab", waiting_delay: "#8944ab", running: "#0071e3", waiting: "#8944ab", queued: "#8e8e93", cancelled: "#8e8e93",
};
