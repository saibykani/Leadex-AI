"use client";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Coins } from "lucide-react";
import { useSession } from "@/lib/session-context";
import { Alert, Button, EmptyState, Input } from "@/components/ui";
import { fmtMoney, label, mkt, type Agreement, type Balance, type Dispute, type Provider, type Referral, type ReferralCommission, type Tx } from "@/lib/marketplace";
import { Field, selectCls } from "../marketplace/_ui";

export default function CommissionsPage() {
  const { can } = useSession();
  const [agreements, setAgreements] = useState<Agreement[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [summary, setSummary] = useState<{ balances: Balance[]; open_disputes: number; transactions: Tx[] } | null>(null);
  const [converted, setConverted] = useState<Referral[]>([]);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [a, s, d] = await Promise.all([mkt.agreements(), mkt.summary(), mkt.disputes()]);
      setAgreements(a); setSummary(s); setDisputes(d);
      if (can("marketplace:write")) {
        const [p, r] = await Promise.all([mkt.providers(), mkt.referrals()]);
        setProviders(p.items); setConverted(r.items.filter((x) => x.status === "converted"));
      }
    } catch (e) { setError((e as Error).message); }
  }, [can]);
  useEffect(() => { if (can("commissions:manage")) void load(); }, [load, can]);

  if (!can("commissions:manage")) return <EmptyState icon={<Coins className="h-5 w-5" />} title="No access" body="You need the commissions:manage permission." />;
  const pname = (id: string) => providers.find((p) => p.id === id)?.business_name ?? id.slice(0, 8);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Commissions</h1>
        <p className="mt-1 text-sm text-muted">Agreements, the append-only ledger and settlements. Figures are computed from ledger entries only.</p>
      </div>
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-4 sm:grid-cols-4">
        {(summary?.balances.length ? summary.balances : [null]).map((b, i) => b ? (
          [["Accrued", b.accrued], ["Paid (net)", String(Number(b.paid) - Number(b.refunded))], ["Settled", b.settled], ["Outstanding", b.outstanding]].map(([l, v]) => (
            <div key={`${b.currency}${l}`} className="card p-5"><div className="text-xs text-muted">{l}</div><div className="mt-1 text-xl font-semibold tabular-nums">{fmtMoney(v, b.currency)}</div></div>
          ))
        ) : <div key={i} className="card p-5 text-sm text-muted sm:col-span-4">No ledger entries yet.</div>)}
      </div>
      <AgreementForm providers={providers} onCreated={load} />
      <section className="card">
        <h2 className="border-b border-line px-5 py-3 text-sm font-medium">Agreements</h2>
        <ul className="divide-y divide-line">
          {agreements.length === 0 && <li className="px-5 py-3 text-sm text-muted">No agreements.</li>}
          {agreements.map((a) => (
            <li key={a.id} className="flex items-center justify-between px-5 py-3 text-sm">
              <span>
                <span className="font-medium">{pname(a.provider_id)}</span> · {label(a.type)} {a.type === "percentage" ? `${Number(a.value)}%` : a.value ? fmtMoney(a.value, a.currency) : ""}
                {a.splits?.length ? <span className="text-muted"> · splits {a.splits.map((s) => `${s.party} ${Number(s.pct)}%`).join(", ")}</span> : null}
                {!a.active && <span className="ml-2 text-xs text-muted">(inactive)</span>}
              </span>
              {a.active && <Button variant="ghost" className="h-9 px-3 text-sm" onClick={async () => { if (confirm("Deactivate this agreement?")) { await mkt.deactivateAgreement(a.id); void load(); } }}>Deactivate</Button>}
            </li>
          ))}
        </ul>
      </section>
      <section className="space-y-3">
        <h2 className="text-sm font-medium">Converted referrals</h2>
        {converted.length === 0 && <p className="text-sm text-muted">No converted referrals.</p>}
        {converted.map((r) => <ReferralLedger key={r.id} r={r} onChange={load} />)}
      </section>
      {disputes.some((d) => d.status === "open") && (
        <section className="card">
          <h2 className="border-b border-line px-5 py-3 text-sm font-medium">Open disputes</h2>
          {disputes.filter((d) => d.status === "open").map((d) => <DisputeRow key={d.id} d={d} onChange={load} />)}
        </section>
      )}
      <section className="card overflow-x-auto">
        <h2 className="border-b border-line px-5 py-3 text-sm font-medium">Ledger</h2>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted"><tr><th className="px-5 py-2">When</th><th>Kind</th><th>Referral</th><th className="text-right">Amount</th><th className="px-5">Reference</th></tr></thead>
          <tbody className="divide-y divide-line">
            {summary?.transactions.map((t) => (
              <tr key={t.id}>
                <td className="px-5 py-2 text-xs text-muted">{new Date(t.created_at).toLocaleString()}</td>
                <td>{label(t.kind)}</td><td className="font-mono text-xs">{t.referral_id.slice(0, 8)}</td>
                <td className="text-right tabular-nums">{fmtMoney(t.amount, t.currency)}</td><td className="px-5 text-xs">{t.reference ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function AgreementForm({ providers, onCreated }: { providers: Provider[]; onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ provider_id: "", type: "percentage", value: "", currency: "INR", splits: "" });
  const [err, setErr] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(null);
    // splits text: "agent:60, partner:40"
    const splits = f.splits.split(",").map((s) => s.trim()).filter(Boolean).map((s) => { const [party, pct] = s.split(":"); return { party: party.trim(), pct: (pct ?? "").trim() }; });
    try {
      await mkt.createAgreement({ provider_id: f.provider_id, type: f.type, value: f.value || null, currency: f.currency, splits });
      setOpen(false); onCreated();
    } catch (e) { setErr((e as Error).message); }
  };
  if (!open) return <Button onClick={() => setOpen(true)}>New agreement</Button>;
  return (
    <form onSubmit={submit} className="card grid gap-4 p-5 md:grid-cols-3">
      {err && <div className="md:col-span-3"><Alert>{err}</Alert></div>}
      <Field label="Provider">
        <select required className={selectCls} value={f.provider_id} onChange={(e) => setF({ ...f, provider_id: e.target.value })}>
          <option value="">Select…</option>{providers.map((p) => <option key={p.id} value={p.id}>{p.business_name}</option>)}
        </select>
      </Field>
      <Field label="Type">
        <select className={selectCls} value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>
          <option value="percentage">Percentage of deal</option><option value="fixed">Fixed amount</option><option value="negotiated">Negotiated per deal</option>
        </select>
      </Field>
      <Field label={f.type === "percentage" ? "Percent" : "Amount"}><Input disabled={f.type === "negotiated"} inputMode="decimal" value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} /></Field>
      <Field label="Currency"><Input maxLength={3} value={f.currency} onChange={(e) => setF({ ...f, currency: e.target.value })} /></Field>
      <div className="md:col-span-2"><Field label="Splits (party:pct, comma separated; total ≤ 100, rest to organization)"><Input value={f.splits} onChange={(e) => setF({ ...f, splits: e.target.value })} placeholder="agent:60, partner:20" /></Field></div>
      <p className="text-xs text-muted md:col-span-3">Default settlement conditions: referral converted, commission fully invoiced and paid, and no open disputes.</p>
      <div className="flex gap-2 md:col-span-3"><Button>Save agreement</Button><Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button></div>
    </form>
  );
}

function ReferralLedger({ r, onChange }: { r: Referral; onChange: () => void }) {
  const [c, setC] = useState<ReferralCommission | null>(null);
  const [amount, setAmount] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => mkt.commission(r.id).then(setC).catch((e) => setErr(e.message)), [r.id]);
  useEffect(() => { void load(); }, [load]);
  const act = async (action: "accrue" | "invoice" | "payment" | "refund" | "settle") => {
    const msg = action === "settle" ? "Settle this commission? Settlement is final and is recorded in the ledger." : `Record ${action}${amount ? ` of ${amount}` : " (full remaining amount)"}?`;
    if (!confirm(msg)) return;
    setErr(null);
    try {
      await mkt.ledger(r.id, action, action === "accrue" ? (amount ? { amount, deal_value: r.deal_value ?? undefined } : {}) : { amount: amount || undefined });
      setAmount(""); await load(); onChange();
    } catch (e) { setErr((e as Error).message); }
  };
  const dispute = async () => {
    const reason = prompt("Dispute reason");
    if (!reason) return;
    try { await mkt.dispute(r.id, reason, amount); await load(); onChange(); } catch (e) { setErr((e as Error).message); }
  };
  const b = c?.balances[0];
  return (
    <div className="card p-5 text-sm">
      <div className="flex flex-wrap justify-between gap-2">
        <div><span className="font-medium">{r.requirement_title}</span> <span className="text-muted">· {r.provider_name}{r.deal_value ? ` · deal ${fmtMoney(r.deal_value, r.currency)}` : ""}</span></div>
        {b && <div className="text-muted">Accrued {fmtMoney(String(Number(b.accrued) - Number(b.reversed)), b.currency)} · Invoiced {fmtMoney(b.invoiced, b.currency)} · Paid {fmtMoney(String(Number(b.paid) - Number(b.refunded)), b.currency)} · Settled {fmtMoney(b.settled, b.currency)}</div>}
      </div>
      {err && <div className="mt-3"><Alert>{err}</Alert></div>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <div className="w-40"><Input className="h-9" placeholder="Amount (optional)" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} /></div>
        {(["accrue", "invoice", "payment", "refund"] as const).map((a) => <Button key={a} variant="outline" className="h-9 px-4 text-sm" onClick={() => act(a)}>{label(a)}</Button>)}
        <Button variant="ghost" className="h-9 px-4 text-sm" onClick={dispute}>Dispute</Button>
        <Button className="h-9 px-4 text-sm" disabled={!c?.settleable} onClick={() => act("settle")}>Settle</Button>
      </div>
      {c && !c.settleable && c.blockers.length > 0 && <p className="mt-2 text-xs text-muted">Cannot settle: {c.blockers.join("; ")}</p>}
    </div>
  );
}

function DisputeRow({ d, onChange }: { d: Dispute; onChange: () => void }) {
  const resolve = async (status: "resolved" | "rejected") => {
    const resolution = prompt(`Resolution note (${status})`);
    if (!resolution) return;
    const reversal = status === "resolved" ? prompt("Reversal amount (leave blank for none)") : null;
    try { await mkt.resolveDispute(d.id, { status, resolution, reversal_amount: reversal || undefined }); onChange(); } catch (e) { alert((e as Error).message); }
  };
  return (
    <div className="flex items-center justify-between border-b border-line px-5 py-3 text-sm last:border-0">
      <span>{d.reason} <span className="text-muted">({d.amount ?? "—"})</span></span>
      <span className="flex gap-2"><Button variant="outline" className="h-9 px-4 text-sm" onClick={() => resolve("resolved")}>Resolve</Button><Button variant="ghost" className="h-9 px-4 text-sm" onClick={() => resolve("rejected")}>Reject</Button></span>
    </div>
  );
}
