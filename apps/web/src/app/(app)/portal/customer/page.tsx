"use client";
import { useEffect, useState } from "react";
import { ClipboardList } from "lucide-react";
import { Alert, EmptyState } from "@/components/ui";
import { fmtMoney, label, mkt, type Requirement } from "@/lib/marketplace";

type Detail = Awaited<ReturnType<typeof mkt.portalCustomer.requirement>>;

export default function CustomerPortal() {
  const [reqs, setReqs] = useState<Requirement[] | null>(null);
  const [open, setOpen] = useState<Record<string, Detail>>({});
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { mkt.portalCustomer.requirements().then(setReqs).catch((e) => setError(e.message)); }, []);
  const toggle = async (id: string) => {
    if (open[id]) { const { [id]: _, ...rest } = open; void _; setOpen(rest); return; }
    try { const d = await mkt.portalCustomer.requirement(id); setOpen({ ...open, [id]: d }); } catch (e) { setError((e as Error).message); }
  };
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">My requirements</h1>
        <p className="mt-1 text-sm text-muted">Requirements recorded under your email address, with matched providers and referral progress.</p>
      </div>
      {error && <Alert>{error}</Alert>}
      {reqs?.length === 0 && <EmptyState icon={<ClipboardList className="h-5 w-5" />} title="No requirements" body="No requirements are linked to your email address in this workspace." />}
      {reqs?.map((r) => (
        <div key={r.id} className="card p-5 text-sm">
          <button className="flex w-full justify-between text-left" onClick={() => toggle(r.id)}>
            <span><span className="font-medium">{r.title}</span><span className="block text-xs text-muted">{[r.city, r.country].filter(Boolean).join(", ")} · {fmtMoney(r.budget_min, r.currency)} – {fmtMoney(r.budget_max, r.currency)}</span></span>
            <span className="text-xs">{label(r.status)}</span>
          </button>
          {open[r.id] && (
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div>
                <h3 className="mb-2 text-xs font-medium text-muted">Matched providers</h3>
                {open[r.id].matches.length === 0 && <p className="text-muted">No matches yet.</p>}
                {open[r.id].matches.map((m, i) => (
                  <div key={i} className="mb-2 rounded-xl bg-raised p-3">
                    <div className="flex justify-between"><span className="font-medium">{m.provider_name}</span><span className="tabular-nums">{m.score}</span></div>
                    {m.unverified && <div className="text-xs text-amber-700">Not verified</div>}
                    <ul className="mt-1 text-xs text-muted">{Object.entries(m.factors).map(([k, v]) => <li key={k}>{label(k)}: {v}</li>)}</ul>
                  </div>
                ))}
              </div>
              <div>
                <h3 className="mb-2 text-xs font-medium text-muted">Referrals</h3>
                {open[r.id].referrals.length === 0 && <p className="text-muted">No referrals yet.</p>}
                {open[r.id].referrals.map((x) => <div key={x.id} className="flex justify-between border-b border-line py-2 last:border-0"><span>{x.provider_name}</span><span>{label(x.status)}</span></div>)}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
