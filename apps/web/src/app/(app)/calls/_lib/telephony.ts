import { api } from "@/lib/api";
import type { CallDetail } from "@/lib/agents";

export type TelephonyStatus = {
  provider: string;
  status: "not_configured" | "needs_public_url" | "configured";
  mode: "not_configured" | "needs_public_url" | "simulated" | "test_allowlist" | "live";
  detail: string;
  credential_source: "org" | "env" | null;
  from_number: string | null;
  public_base_url: string | null;
  app_env: string;
  allow_test_calls: boolean;
  test_allowlist: string[];
  voice_webhook_example: string | null;
};

export type CallOutcome = {
  interest: string; budget_min: number | null; budget_max: number | null; budget_currency: string | null;
  budget_evidence: string | null; timeline: string | null; timeline_evidence: string | null;
  decision_maker: string | null; next_step: string | null; summary: string; extraction_mode: string; created_at: string;
};

export type TelephonyCallDetail = CallDetail & {
  provider_call_id?: string | null; to_number?: string | null; error_message?: string | null;
  price?: number | null; price_unit?: string | null; outcome?: CallOutcome | null;
};

export const ACTIVE_STATUSES = new Set(["queued", "initiated", "ringing", "in_progress"]);

export const telephonyApi = {
  status: () => api<TelephonyStatus>("/telephony/status", {}, true),
  call: (id: string) => api<TelephonyCallDetail>(`/calls/${id}`, {}, true),
};
