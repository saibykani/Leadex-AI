"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { reasonLabel } from "@/lib/agents";
import { api } from "@/lib/api";
import { Alert } from "@/components/ui";
import { SimulatedBadge, StatusBadge } from "../../agents/_ui";
import { ACTIVE_STATUSES, telephonyApi, type CallOutcome, type TelephonyCallDetail } from "../_lib/telephony";

const fmtMoney = (v: number | null, cur: string | null) => (v == null ? null : `${cur ?? ""} ${v.toLocaleString()}`.trim());

function OutcomeCard({ o }: { o: CallOutcome }) {
  const budget = o.budget_min != null || o.budget_max != null
    ? o.budget_min != null && o.budget_max != null && o.budget_min !== o.budget_max
      ? `${fmtMoney(o.budget_min, o.budget_currency)} – ${fmtMoney(o.budget_max, null)}`
      : fmtMoney(o.budget_max ?? o.budget_min, o.budget_currency)
    : null;
  return (
    <div className="card p-5">
      <h2 className="mb-3 text-sm font-medium">Outcome <span className="ml-2 text-xs font-normal text-muted">extraction: {o.extraction_mode}</span></h2>
      <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
        <div><dt className="text-xs text-muted">Interest</dt><dd className="capitalize">{o.interest}</dd></div>
        <div><dt className="text-xs text-muted">Next step</dt><dd>{o.next_step ?? "—"}</dd></div>
        <div><dt className="text-xs text-muted">Budget</dt><dd>{budget ?? "Not stated"}</dd>
          {o.budget_evidence && <dd className="mt-0.5 text-xs italic text-muted">&ldquo;{o.budget_evidence}&rdquo;</dd>}</div>
        <div><dt className="text-xs text-muted">Timeline</dt><dd>{o.timeline ?? "Not stated"}</dd>
          {o.timeline_evidence && <dd className="mt-0.5 text-xs italic text-muted">&ldquo;{o.timeline_evidence}&rdquo;</dd>}</div>
        {o.decision_maker && <div><dt className="text-xs text-muted">Decision maker</dt><dd>{o.decision_maker}</dd></div>}
      </dl>
      {o.summary && <p className="mt-3 text-sm text-muted">{o.summary}</p>}
    </div>
  );
}

export default function CallDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [call, setCall] = useState<TelephonyCallDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const active = call ? ACTIVE_STATUSES.has(call.status) : true;

  useEffect(() => {
    let alive = true;
    const load = () => telephonyApi.call(id).then((c) => { if (alive) { setCall(c); setError(null); } })
      .catch((e) => { if (alive) setError(e.message); });
    load();
    if (!active) return () => { alive = false; };
    const t = setInterval(load, 3000);  // live updates while the call is in progress
    return () => { alive = false; clearInterval(t); };
  }, [id, active]);

  if (error && !call) return <Alert>{error}</Alert>;
  if (!call) return <p className="text-sm text-muted">Loading…</p>;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <Link href="/calls" className="text-sm text-accent">← Call history</Link>
        <h1 className="mt-1 flex items-center gap-3 text-xl font-semibold">Call <StatusBadge status={call.status} /><SimulatedBadge on={call.simulated && call.status !== "blocked"} />
          {active && <span className="flex items-center gap-1.5 text-xs font-normal text-accent"><span className="h-2 w-2 animate-pulse rounded-full bg-accent" />live</span>}</h1>
        <p className="mt-1 text-sm text-muted">{new Date(call.created_at).toLocaleString()} · {call.direction} · {call.language.toUpperCase()} · provider {call.provider}
          {call.agent_version ? ` · agent v${call.agent_version}` : ""}
          {call.to_number ? ` · to ${call.to_number}` : ""}
          {call.duration_s != null && !call.simulated ? ` · ${call.duration_s}s` : ""}
          {call.price != null ? ` · cost ${call.price} ${call.price_unit ?? ""}` : ""}</p>
        <p className="mt-1 text-sm"><Link className="text-accent" href={`/agents/${call.agent_id}`}>Agent</Link> · <Link className="text-accent" href={`/leads/${call.lead_id}`}>Lead</Link></p>
      </div>

      {error && <Alert>{error}</Alert>}
      {call.error_message && (
        <div className="card p-5">
          <h2 className="mb-1 text-sm font-medium text-danger">{call.provider === "twilio" ? "Twilio error" : "Telephony"}</h2>
          <p className="break-words font-mono text-xs">{call.error_message}</p>
          {/21219|unverified/i.test(call.error_message) && <p className="mt-2 text-xs text-muted">Twilio trial accounts can only call numbers verified in the Twilio console (Verified Caller IDs).</p>}
        </div>
      )}

      {(call.gate_reasons ?? []).length > 0 && (
        <div className="card p-5">
          <h2 className="mb-2 text-sm font-medium text-danger">{call.status === "not_configured" ? "Not placed — configuration" : "Blocked — reasons"}</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm">{call.gate_reasons!.map((r) => <li key={r}>{reasonLabel(r)} <span className="font-mono text-xs text-muted">{r}</span></li>)}</ul>
        </div>
      )}

      {call.outcome && <OutcomeCard o={call.outcome} />}
      {!call.simulated && !active && call.transcript.length > 0 && <RateCall id={call.id} />}

      <div className="card p-5">
        <h2 className="mb-2 text-sm font-medium">Transcript</h2>
        {call.transcript.length === 0 ? <p className="text-sm text-muted">{active ? "Waiting for the call to be answered…" : "No transcript."}</p> : (
          <ul className="space-y-3 text-sm">{call.transcript.map((t) => (
            <li key={t.seq} className={t.speaker === "contact" ? "pl-8" : ""}>
              <span className="font-medium capitalize">{t.speaker === "agent" ? "AI agent" : t.speaker}</span>
              <span className="ml-2 text-xs text-muted">{new Date(t.created_at).toLocaleTimeString()}</span>
              {t.simulated && <span className="ml-2"><SimulatedBadge /></span>}
              <p className="mt-0.5 text-muted">{t.text}</p></li>
          ))}</ul>
        )}
        {call.summary && <p className="mt-4 text-sm"><b>Summary:</b> {call.summary.summary}</p>}
        {call.recording && <p className="mt-2 text-xs text-muted">Recording: {call.recording.enabled ? `enabled (consent ${call.recording.consent_reference})` : "disabled (no recording consent)"}</p>}
      </div>

      <div className="card p-5">
        <h2 className="mb-2 text-sm font-medium">Events</h2>
        <ol className="space-y-1 text-sm">{call.events.map((e) => (
          <li key={e.id} className="flex gap-3"><span className="whitespace-nowrap text-muted">{new Date(e.created_at).toLocaleTimeString()}</span><span className="font-mono text-xs">{e.type}</span>
            {e.data && Object.keys(e.data).length > 0 && <span className="truncate text-xs text-muted">{JSON.stringify(e.data)}</span>}</li>
        ))}</ol>
      </div>
    </div>
  );
}

/** Human rating of a real call. Overrides the automatic score used by the agent's self-learning. */
function RateCall({ id }: { id: string }) {
  const [note, setNote] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function rate(good: boolean) {
    setErr(null);
    try {
      await api(`/calls/${id}/feedback`, { method: "POST", body: JSON.stringify({ good, note: note || undefined }) }, true);
      setDone(good ? "Marked as a good call. The agent will learn from it." : "Marked as a bad call. The agent will avoid this approach.");
    } catch (e) { setErr((e as Error).message); }
  }
  return (
    <div className="card space-y-3 p-5">
      <h2 className="text-sm font-medium">Teach the agent</h2>
      {done ? <p className="text-sm text-muted">{done}</p> : (
        <>
          <input className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-sm" placeholder="Optional note (what went well or wrong)" value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
          <div className="flex gap-2">
            <button className="rounded-full bg-green-600 px-4 py-2 text-sm font-medium text-white" onClick={() => rate(true)}>👍 Good call</button>
            <button className="rounded-full border border-line px-4 py-2 text-sm font-medium" onClick={() => rate(false)}>👎 Bad call</button>
          </div>
        </>
      )}
      {err && <p className="text-sm text-danger">{err}</p>}
    </div>
  );
}
