"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useSession } from "@/lib/session-context";
import { Alert, Button, Input } from "@/components/ui";
import {
  campaigns, email, newIdempotencyKey, type Approval, type CampaignDetail, type CampaignEvent, type EmailAnalytics, type Recipient,
} from "@/lib/communication";
import { Badge } from "../_ui/badge";

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { can, me } = useSession();
  const [c, setC] = useState<CampaignDetail | null>(null);
  const [recipients, setRecipients] = useState<Recipient[]>([]);
  const [events, setEvents] = useState<CampaignEvent[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [stats, setStats] = useState<EmailAnalytics | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [startKey] = useState(newIdempotencyKey);

  const load = useCallback(() => {
    campaigns.get(id).then(setC).catch((e) => setError(e.message));
    campaigns.recipients(id).then((p) => setRecipients(p.items)).catch(() => {});
    campaigns.events(id).then((p) => setEvents(p.items)).catch(() => {});
    campaigns.approvals(id).then(setApprovals).catch(() => {});
    email.analytics(id).then(setStats).catch(() => {});
  }, [id]);
  useEffect(load, [load]);

  const run = async (fn: () => Promise<unknown>, msg?: (r: unknown) => string) => {
    setError(null); setInfo(null); setBusy(true);
    try { const r = await fn(); if (msg) setInfo(msg(r)); load(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const fmt = (r: unknown) => {
    const d = (r as { dispatched?: Record<string, number>; replayed?: boolean }) ?? {};
    const parts = Object.entries(d.dispatched ?? {}).map(([k, v]) => `${v} ${k}`);
    return `${d.replayed ? "Already started (replayed). " : ""}${parts.length ? parts.join(", ") : "Nothing due"}`;
  };

  if (!c) return error ? <Alert>{error}</Alert> : <div className="text-sm text-muted">Loading…</div>;
  const isCreator = c.created_by_user_id === me.user.id;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{c.name}</h1>
          <p className="mt-1 text-sm capitalize text-muted">{c.channel} campaign</p>
        </div>
        <Badge value={c.status} />
      </div>
      {error && <Alert>{error}</Alert>}
      {info && <div className="rounded-lg border border-line bg-raised px-3 py-2 text-sm">{info}</div>}

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="card space-y-3 p-5 lg:col-span-2">
          <h2 className="text-sm font-medium">Actions</h2>
          <div className="flex flex-wrap gap-2">
            {c.status === "draft" && can("campaigns:write") && <Button loading={busy} onClick={() => run(() => campaigns.submit(id))}>Submit for approval</Button>}
            {(c.status === "approved" || c.status === "paused") && can("campaigns:write") && (
              <Button loading={busy} onClick={() => run(() => campaigns.start(id, startKey), fmt)}>{c.status === "paused" ? "Resume" : "Start"}</Button>
            )}
            {c.status === "running" && can("campaigns:write") && (<>
              <Button variant="outline" loading={busy} onClick={() => run(() => campaigns.tick(id), fmt)}>Process due steps</Button>
              <Button variant="outline" onClick={() => run(() => campaigns.pause(id))}>Pause</Button>
            </>)}
            {!["completed", "cancelled"].includes(c.status) && can("campaigns:write") && <Button variant="ghost" onClick={() => run(() => campaigns.cancel(id))}>Cancel</Button>}
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            {Object.entries(c.recipient_counts).map(([k, v]) => <span key={k} className="rounded-full bg-raised px-2.5 py-1">{v} {k}</span>)}
          </div>
          {c.channel === "email" && stats && (
            <p className="text-xs text-muted">Email: {stats.sent} sent · {stats.delivered} delivered · {stats.bounced} bounced · {stats.replied} replied · {stats.simulated} simulated · {stats.blocked} blocked</p>
          )}
        </section>

        <section className="card space-y-3 p-5">
          <h2 className="text-sm font-medium">Approval</h2>
          {c.status === "pending_approval" && can("campaigns:approve") ? (
            <>
              {isCreator && <p className="text-xs text-muted">You created this campaign. Another member must approve it unless you are the only member of this workspace.</p>}
              <Input placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
              <div className="flex gap-2">
                <Button loading={busy} onClick={() => run(() => campaigns.decide(id, "approved", note || undefined))}>Approve</Button>
                <Button variant="outline" onClick={() => run(() => campaigns.decide(id, "rejected", note || undefined))}>Reject</Button>
              </div>
            </>
          ) : <p className="text-xs text-muted">{c.status === "pending_approval" ? "Waiting for an approver." : c.approved_at ? `Approved ${new Date(c.approved_at).toLocaleString()}` : "Not yet submitted."}</p>}
          <ul className="space-y-1 text-xs">
            {approvals.map((a) => <li key={a.id}><Badge value={a.decision} /> <span className="text-muted">{new Date(a.created_at).toLocaleString()}</span>{a.note ? ` — ${a.note}` : ""}</li>)}
          </ul>
        </section>
      </div>

      <section className="card overflow-x-auto">
        <h2 className="border-b border-line px-5 py-3 text-sm font-medium">Recipients &amp; gate results</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted"><tr><th className="px-5 py-2">Lead</th><th>Status</th><th>Gate</th><th>Reasons</th><th>Step</th><th>Next due</th></tr></thead>
          <tbody className="divide-y divide-line">
            {recipients.map((r) => (
              <tr key={r.id}>
                <td className="px-5 py-2">{r.business_name ?? r.lead_id}</td>
                <td><Badge value={r.status} /></td>
                <td className="text-xs">{r.gate_allowed == null ? "—" : r.gate_allowed ? (r.gate_simulated ? "allowed (simulated env)" : "allowed") : "blocked"}</td>
                <td className="max-w-[320px] text-xs text-muted">{r.gate_reasons?.join(", ")}</td>
                <td className="text-xs">{r.current_step + 1}</td>
                <td className="text-xs text-muted">{r.next_due_at ? new Date(r.next_due_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {recipients.length === 0 && <p className="px-5 py-6 text-sm text-muted">No recipients.</p>}
      </section>

      <section className="card">
        <h2 className="border-b border-line px-5 py-3 text-sm font-medium">Timeline</h2>
        <ol className="divide-y divide-line">
          {events.map((e) => (
            <li key={e.id} className="flex justify-between gap-4 px-5 py-2.5 text-sm">
              <span><span className="font-mono text-xs">{e.type}</span>{e.data ? <span className="ml-2 text-xs text-muted">{JSON.stringify(e.data)}</span> : null}</span>
              <time className="whitespace-nowrap text-xs text-muted">{new Date(e.created_at).toLocaleString()}</time>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
