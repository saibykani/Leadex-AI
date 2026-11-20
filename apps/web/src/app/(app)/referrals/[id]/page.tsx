"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { useSession } from "@/lib/session-context";
import { Alert, Button, Input } from "@/components/ui";
import { NEXT, fmtMoney, label, mkt, type RefEvent, type Referral, type ReferralCommission } from "@/lib/marketplace";

export default function ReferralDetail() {
  const { id } = useParams<{ id: string }>();
  const { can } = useSession();
  const [r, setR] = useState<Referral | null>(null);
  const [events, setEvents] = useState<RefEvent[]>([]);
  const [com, setCom] = useState<ReferralCommission | null>(null);
  const [deal, setDeal] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [a, b] = await Promise.all([mkt.referral(id), mkt.events(id)]);
      setR(a); setEvents(b);
      if (can("commissions:manage")) setCom(await mkt.commission(id));
    } catch (e) { setError((e as Error).message); }
  }, [id, can]);
  useEffect(() => { void load(); }, [load]);

  const move = async (s: string) => {
    if (["lost", "declined", "converted"].includes(s) && !confirm(`Move referral to "${label(s)}"? This is final.`)) return;
    setError(null);
    try { await mkt.setStatus(id, s, s === "converted" && deal ? { deal_value: deal } : {}); await load(); } catch (e) { setError((e as Error).message); }
  };

  if (!r) return error ? <Alert>{error}</Alert> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-6">
      <Link href="/referrals" className="inline-flex items-center gap-1 text-sm text-muted hover:text-neutral-900"><ArrowLeft className="h-4 w-4" />Referrals</Link>
      <div>
        <h1 className="text-xl font-semibold">{r.requirement_title}</h1>
        <p className="mt-1 text-sm text-muted">{r.provider_name} · <span className="font-medium text-neutral-900">{label(r.status)}</span>{r.deal_value ? ` · deal ${fmtMoney(r.deal_value, r.currency)}` : ""}</p>
      </div>
      {error && <Alert>{error}</Alert>}
      {NEXT[r.status]?.length > 0 && (
        <section className="card flex flex-wrap items-end gap-2 p-5">
          {NEXT[r.status].includes("converted") && <div className="w-48"><Input placeholder={`Deal value (${r.currency})`} inputMode="decimal" value={deal} onChange={(e) => setDeal(e.target.value)} /></div>}
          {NEXT[r.status].map((s) => <Button key={s} variant={["lost", "declined"].includes(s) ? "ghost" : "outline"} onClick={() => move(s)}>{label(s)}</Button>)}
        </section>
      )}
      {com && (
        <section className="card p-5 text-sm">
          <div className="flex items-center justify-between"><h2 className="font-medium">Commission</h2><Link className="text-accent" href="/commissions">Manage →</Link></div>
          {com.balances.map((b) => <p key={b.currency} className="mt-2 text-muted">Accrued {fmtMoney(b.accrued, b.currency)} · Paid {fmtMoney(b.paid, b.currency)} · Settled {fmtMoney(b.settled, b.currency)}</p>)}
          {com.blockers.length > 0 && <p className="mt-2 text-xs text-muted">Settlement blocked: {com.blockers.join("; ")}</p>}
        </section>
      )}
      <section className="card">
        <h2 className="border-b border-line px-5 py-3 text-sm font-medium">Timeline</h2>
        <ul className="divide-y divide-line">
          {events.map((e) => (
            <li key={e.id} className="flex justify-between px-5 py-2.5 text-sm">
              <span>{e.from_status ? `${label(e.from_status)} → ` : ""}{e.to_status ? label(e.to_status) : e.type}{e.note ? <span className="text-muted"> — {e.note}</span> : null}</span>
              <time className="text-xs text-muted">{new Date(e.created_at).toLocaleString()}</time>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
