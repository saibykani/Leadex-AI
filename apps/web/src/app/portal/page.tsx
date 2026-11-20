"use client";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Alert, Badge, Button } from "@/components/ui";
import { portal, portalToken, type CustomerReq, type Money, type PortalMe, type ProviderRef } from "@/lib/portal";

const label = (s: string) => s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
const money = (v: string | null, c: string) => (v == null ? "—" : `${c} ${Number(v).toLocaleString()}`);

export default function PortalHome() {
  const router = useRouter();
  const [me, setMe] = useState<PortalMe | null>(null);
  useEffect(() => {
    if (!portalToken.get()) { router.replace("/portal/login"); return; }
    portal.me().then(setMe).catch(() => router.replace("/portal/login"));
  }, [router]);
  const signOut = () => { portalToken.clear(); router.replace("/portal/login"); };
  if (!me) return <main className="flex min-h-screen items-center justify-center bg-[#f6f5ff] text-sm text-neutral-600">Loading…</main>;
  return (
    <main className="min-h-screen bg-[#f6f5ff] px-4 py-8">
      <div className="mx-auto max-w-3xl space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">{me.role === "provider" ? "Provider portal" : "Customer portal"}</h1>
            <p className="text-sm text-neutral-600">{me.email}</p>
          </div>
          <Button variant="outline" className="h-9 px-4 text-sm" onClick={signOut}>Sign out</Button>
        </header>
        {me.role === "provider" ? <Provider /> : <Customer />}
      </div>
    </main>
  );
}

function Provider() {
  const [refs, setRefs] = useState<ProviderRef[]>([]);
  const [totals, setTotals] = useState<Money[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { const [r, c] = await Promise.all([portal.provider.referrals(), portal.provider.commissions()]); setRefs(r); setTotals(c.totals); }
    catch (e) { setError((e as Error).message); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const act = async (fn: () => Promise<unknown>) => { setError(null); try { await fn(); await load(); } catch (e) { setError((e as Error).message); } };
  return (
    <>
      {error && <Alert>{error}</Alert>}
      <section className="rounded-3xl bg-white p-5 ring-1 ring-black/5">
        <h2 className="font-medium">Commission status</h2>
        {totals.length === 0 ? <p className="mt-2 text-sm text-neutral-600">No commission has been recorded yet.</p> : totals.map((t) => (
          <dl key={t.currency} className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            {(["accrued", "invoiced", "paid", "outstanding"] as const).map((k) => <div key={k}><dt className="text-neutral-500">{label(k)}</dt><dd className="font-medium">{money(t[k], t.currency)}</dd></div>)}
          </dl>
        ))}
      </section>
      <section className="space-y-3">
        <h2 className="font-medium">Referrals sent to you</h2>
        {refs.length === 0 && <p className="text-sm text-neutral-600">No referrals yet.</p>}
        {refs.map((r) => (
          <div key={r.id} className="rounded-3xl bg-white p-5 ring-1 ring-black/5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <div className="font-medium">{r.requirement.title}</div>
                <div className="text-xs text-neutral-500">{[r.requirement.city, r.requirement.country].filter(Boolean).join(", ") || "Any location"} · {money(r.requirement.budget_min, r.requirement.currency)} – {money(r.requirement.budget_max, r.requirement.currency)}{r.requirement.timeline ? ` · ${r.requirement.timeline}` : ""}</div>
              </div>
              <Badge>{label(r.status)}</Badge>
            </div>
            {r.requirement.description && <p className="mt-2 text-sm text-neutral-700">{r.requirement.description}</p>}
            {r.customer && <p className="mt-2 text-sm">Customer: <strong>{r.customer.full_name}</strong> · {r.customer.email}{r.customer.phone ? ` · ${r.customer.phone}` : ""}</p>}
            {r.status === "invited" && (
              <div className="mt-3 flex gap-2">
                <Button className="h-9 px-4 text-sm" onClick={() => act(() => portal.provider.accept(r.id))}>Accept</Button>
                <Button variant="outline" className="h-9 px-4 text-sm" onClick={() => act(() => portal.provider.decline(r.id))}>Decline</Button>
              </div>
            )}
          </div>
        ))}
      </section>
    </>
  );
}

function Customer() {
  const [reqs, setReqs] = useState<CustomerReq[]>([]);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => { try { setReqs(await portal.customer.requirements()); } catch (e) { setError((e as Error).message); } }, []);
  useEffect(() => { void load(); }, [load]);
  const withdraw = async (id: string) => {
    if (!window.confirm("Withdraw permission to share your requirement and contact details with providers?")) return;
    setError(null);
    try { await portal.customer.withdraw(id); await load(); } catch (e) { setError((e as Error).message); }
  };
  return (
    <section className="space-y-3">
      {error && <Alert>{error}</Alert>}
      <h2 className="font-medium">Your requirements</h2>
      {reqs.length === 0 && <p className="text-sm text-neutral-600">No requirements found.</p>}
      {reqs.map((r) => (
        <div key={r.id} className="rounded-3xl bg-white p-5 ring-1 ring-black/5">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="font-medium">{r.title}</div>
              <div className="text-xs text-neutral-500">{[r.city, r.country].filter(Boolean).join(", ") || "Any location"}{r.timeline ? ` · ${r.timeline}` : ""}</div>
            </div>
            <div className="flex gap-2"><Badge>{label(r.status)}</Badge>{r.contact_permission ? <Badge tone="success">Contact permitted</Badge> : <Badge tone="warning">Contact withdrawn</Badge>}</div>
          </div>
          <h3 className="mt-3 text-sm font-medium">Referred providers</h3>
          {r.referrals.length === 0 ? <p className="text-sm text-neutral-600">Not referred to any provider yet.</p> : (
            <ul className="mt-1 divide-y divide-neutral-100 text-sm">
              {r.referrals.map((x) => <li key={x.id} className="flex justify-between py-1.5"><span>{x.provider_name ?? "Provider"}</span><Badge>{label(x.status)}</Badge></li>)}
            </ul>
          )}
          {r.contact_permission && <Button variant="outline" className="mt-3 h-9 px-4 text-sm" onClick={() => withdraw(r.id)}>Withdraw contact permission</Button>}
        </div>
      ))}
    </section>
  );
}
