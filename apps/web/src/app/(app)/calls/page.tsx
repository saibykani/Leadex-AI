"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { PhoneCall } from "lucide-react";
import { callsApi, reasonLabel, type Call } from "@/lib/agents";
import { Alert, EmptyState } from "@/components/ui";
import { SimulatedBadge, StatusBadge } from "../agents/_ui";
import { TelephonyCard } from "./TelephonyCard";

const STATUSES = ["", "blocked", "simulated_completed", "not_configured", "initiated", "ringing", "in_progress", "completed", "busy", "no_answer", "failed", "canceled"];

export default function CallsPage() {
  const [calls, setCalls] = useState<Call[] | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCalls(null);
    callsApi.list(status ? `&status=${status}` : "").then((p) => setCalls(p.items)).catch((e) => setError(e.message));
  }, [status]);

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Call history</h1>
          <p className="mt-1 text-sm text-muted">Every call request is recorded, including those blocked by compliance checks. Real calls go through Twilio only when telephony is configured and the environment allows it (see below); otherwise allowed calls are simulated.</p>
        </div>
        <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)} className="h-10 rounded-lg border border-line bg-bg px-3 text-sm">
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s.replace(/_/g, " ") : "All statuses"}</option>)}
        </select>
      </div>
      <TelephonyCard />
      {error && <Alert>{error}</Alert>}
      {calls === null ? <p className="text-sm text-muted">Loading…</p> : calls.length === 0 ? (
        <EmptyState icon={<PhoneCall className="h-5 w-5" />} title="No calls" body="Calls are started from a lead with a published agent." />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-line text-left text-xs text-muted">
              <tr><th className="px-4 py-3">When</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Reasons</th><th className="px-4 py-3">Lang</th><th className="px-4 py-3" /></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {calls.map((c) => (
                <tr key={c.id} className="hover:bg-raised">
                  <td className="px-4 py-3 whitespace-nowrap">{new Date(c.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3"><span className="flex items-center gap-2"><StatusBadge status={c.status} /><SimulatedBadge on={c.simulated && c.status !== "blocked"} /></span></td>
                  <td className="px-4 py-3 text-muted">{(c.gate_reasons ?? []).map(reasonLabel).join("; ") || "—"}</td>
                  <td className="px-4 py-3 uppercase">{c.language}</td>
                  <td className="px-4 py-3 text-right"><Link href={`/calls/${c.id}`} className="text-accent">Details</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
