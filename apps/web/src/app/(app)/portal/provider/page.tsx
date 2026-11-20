"use client";
import { useCallback, useEffect, useState } from "react";
import { Briefcase } from "lucide-react";
import { Alert, Button, EmptyState, Input } from "@/components/ui";
import { NEXT, PROVIDER_ALLOWED, fmtMoney, label, mkt, type Balance, type PortalReferral, type Provider } from "@/lib/marketplace";

export default function ProviderPortal() {
  const [profile, setProfile] = useState<Provider[] | null>(null);
  const [refs, setRefs] = useState<PortalReferral[]>([]);
  const [earn, setEarn] = useState<Balance[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      const [p, r, e] = await Promise.all([mkt.portalProvider.profile(), mkt.portalProvider.referrals(), mkt.portalProvider.earnings()]);
      setProfile(p); setRefs(r); setEarn(e);
    } catch (e) { setError((e as Error).message); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  if (profile && profile.length === 0) {
    return <EmptyState icon={<Briefcase className="h-5 w-5" />} title="Not linked to a provider" body="Ask the workspace administrator to link your account to your provider profile." />;
  }
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Provider portal</h1>
        <p className="mt-1 text-sm text-muted">{profile?.map((p) => p.business_name).join(", ")}</p>
      </div>
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-4 sm:grid-cols-3">
        {earn.map((b) => [["Commission accrued", String(Number(b.accrued) - Number(b.reversed))], ["Paid", String(Number(b.paid) - Number(b.refunded))], ["Settled", b.settled]].map(([l, v]) => (
          <div key={b.currency + l} className="card p-5"><div className="text-xs text-muted">{l}</div><div className="mt-1 text-xl font-semibold">{fmtMoney(v, b.currency)}</div></div>
        )))}
      </div>
      {refs.length === 0 && <EmptyState icon={<Briefcase className="h-5 w-5" />} title="No referrals yet" body="Referrals sent to you will appear here." />}
      {refs.map((r) => <Row key={r.id} r={r} onChange={load} />)}
    </div>
  );
}

function Row({ r, onChange }: { r: PortalReferral; onChange: () => void }) {
  const [err, setErr] = useState<string | null>(null);
  const [deal, setDeal] = useState("");
  const run = async (fn: () => Promise<unknown>) => { setErr(null); try { await fn(); onChange(); } catch (e) { setErr((e as Error).message); } };
  const nexts = (NEXT[r.status] ?? []).filter((s) => PROVIDER_ALLOWED.has(s) && s !== "accepted" && s !== "declined");
  return (
    <div className="card p-5 text-sm">
      <div className="flex justify-between gap-3">
        <div>
          <div className="font-medium">{r.requirement.title}</div>
          <div className="text-xs text-muted">{[r.requirement.city, r.requirement.country].filter(Boolean).join(", ")} · {fmtMoney(r.requirement.budget_min, r.requirement.currency)} – {fmtMoney(r.requirement.budget_max, r.requirement.currency)}{r.requirement.timeline ? ` · ${r.requirement.timeline}` : ""}</div>
        </div>
        <span className="text-xs font-medium">{label(r.status)}</span>
      </div>
      {r.requirement.description && <p className="mt-2 text-muted">{r.requirement.description}</p>}
      {r.customer ? <p className="mt-2">Contact: {r.customer.full_name} · {r.customer.email}{r.customer.phone ? ` · ${r.customer.phone}` : ""}</p>
        : <p className="mt-2 text-xs text-muted">Customer contact details are shared after you accept (and only with the customer&apos;s permission).</p>}
      {err && <div className="mt-3"><Alert>{err}</Alert></div>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {r.status === "invited" && <>
          <Button className="h-9 px-4 text-sm" onClick={() => run(() => mkt.portalProvider.accept(r.id))}>Accept</Button>
          <Button variant="ghost" className="h-9 px-4 text-sm" onClick={() => confirm("Decline this referral?") && run(() => mkt.portalProvider.decline(r.id))}>Decline</Button>
        </>}
        {nexts.includes("converted") && <div className="w-44"><Input className="h-9" placeholder="Deal value" inputMode="decimal" value={deal} onChange={(e) => setDeal(e.target.value)} /></div>}
        {nexts.map((s) => <Button key={s} variant="outline" className="h-9 px-4 text-sm" onClick={() => (s !== "lost" && s !== "converted") || confirm(`Mark as ${label(s)}?`) ? run(() => mkt.portalProvider.status(r.id, s, s === "converted" ? deal : undefined)) : undefined}>{label(s)}</Button>)}
      </div>
    </div>
  );
}
