"use client";
import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Store } from "lucide-react";
import { useSession } from "@/lib/session-context";
import { Alert, Button, EmptyState, Input } from "@/components/ui";
import { fmtMoney, label, mkt, type Category, type Match, type Provider, type Requirement } from "@/lib/marketplace";
import { InviteToPortal } from "./_invite";
import { Badge, Field, MatchCard, Tabs, VerificationBadge, areaCls, selectCls } from "./_ui";

export default function MarketplacePage() {
  const { can } = useSession();
  const [tab, setTab] = useState<"requirements" | "providers">("requirements");
  const [cats, setCats] = useState<Category[]>([]);
  const [reqs, setReqs] = useState<Requirement[]>([]);
  const [provs, setProvs] = useState<Provider[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [c, r, p] = await Promise.all([mkt.categories(), mkt.requirements(), mkt.providers()]);
      setCats(c); setReqs(r.items); setProvs(p.items);
    } catch (e) { setError((e as Error).message); }
  }, []);
  useEffect(() => { if (can("marketplace:write")) void load(); }, [load, can]);

  if (!can("marketplace:write")) {
    return <EmptyState icon={<Store className="h-5 w-5" />} title="No access" body="You need the marketplace:write permission. Provider and customer portals are under Portal." />;
  }
  const catName = (id: string) => cats.find((c) => c.id === id)?.name ?? "—";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Marketplace</h1>
          <p className="mt-1 text-sm text-muted">Match customer requirements with service providers.</p>
        </div>
        <Tabs value={tab} onChange={setTab} options={[["requirements", "Requirements"], ["providers", "Providers"]]} />
      </div>
      {error && <Alert>{error}</Alert>}
      {tab === "requirements" ? (
        <>
          <RequirementForm cats={cats} onCreated={load} />
          {reqs.length === 0 ? <EmptyState icon={<Store className="h-5 w-5" />} title="No requirements yet" body="Capture a customer requirement to start matching." />
            : <div className="space-y-3">{reqs.map((r) => <RequirementRow key={r.id} r={r} catName={catName(r.category_id)} onChange={load} />)}</div>}
        </>
      ) : (
        <>
          <ProviderForm cats={cats} onCreated={load} />
          <div className="card divide-y divide-line">
            {provs.length === 0 && <p className="p-5 text-sm text-muted">No providers yet.</p>}
            {provs.map((p) => (
              <Link key={p.id} href={`/marketplace/providers/${p.id}`} className="flex items-center justify-between px-5 py-3 hover:bg-raised">
                <div>
                  <div className="font-medium">{p.business_name}</div>
                  <div className="text-xs text-muted">{p.category_ids.map(catName).join(", ") || "No categories"} · {(p.service_areas ?? []).map((a) => a.city ?? a.country).join(", ") || "No service areas"}</div>
                </div>
                <VerificationBadge status={p.verification_status} />
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function RequirementRow({ r, catName, onChange }: { r: Requirement; catName: string; onChange: () => void }) {
  const [matches, setMatches] = useState<Match[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [referred, setReferred] = useState<Set<string>>(new Set());
  const run = async () => {
    setBusy(true); setMsg(null);
    try { setMatches(await mkt.match(r.id)); onChange(); } catch (e) { setMsg((e as Error).message); } finally { setBusy(false); }
  };
  const refer = async (pid: string) => {
    setMsg(null);
    try { await mkt.createReferral(r.id, pid); setReferred((s) => new Set(s).add(pid)); setMsg("Referral created."); onChange(); } catch (e) { setMsg((e as Error).message); }
  };
  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-medium">{r.title}</div>
          <div className="mt-0.5 text-xs text-muted">{catName} · {[r.city, r.country].filter(Boolean).join(", ") || "Any location"}{r.budget_min || r.budget_max ? ` · ${fmtMoney(r.budget_min, r.currency)} – ${fmtMoney(r.budget_max, r.currency)}` : " · Budget not stated"}{r.timeline ? ` · ${r.timeline}` : ""}</div>
          <div className="mt-2 flex gap-2"><Badge>{label(r.status)}</Badge>{r.contact_permission ? <Badge tone="good">Contact permitted</Badge> : <Badge tone="warn">No contact permission</Badge>}</div>
        </div>
        <div className="flex flex-col items-end gap-2"><Button variant="outline" loading={busy} onClick={run}>Run matching</Button><InviteToPortal kind="requirement" id={r.id} /></div>
      </div>
      {msg && <p className="mt-3 text-sm text-muted">{msg}</p>}
      {matches && (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {matches.length === 0 && <p className="text-sm text-muted">No eligible providers.</p>}
          {matches.map((m) => (
            <MatchCard key={m.id} m={m} action={!r.contact_permission ? undefined : referred.has(m.provider_id) ? <Badge tone="good">Referred</Badge> : <Button variant="outline" className="h-9 px-4 text-sm" onClick={() => refer(m.provider_id)}>Refer</Button>} />
          ))}
        </div>
      )}
    </div>
  );
}

function RequirementForm({ cats, onCreated }: { cats: Category[]; onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ full_name: "", email: "", phone: "", category_id: "", title: "", city: "", country: "", budget_min: "", budget_max: "", currency: "INR", timeline: "", description: "", contact_permission: false, consent_reference: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      await mkt.createRequirement({
        customer: { full_name: f.full_name, email: f.email, phone: f.phone || null }, category_id: f.category_id, title: f.title,
        city: f.city || null, country: f.country || null, budget_min: f.budget_min || null, budget_max: f.budget_max || null,
        currency: f.currency, timeline: f.timeline || null, description: f.description || null,
        contact_permission: f.contact_permission, consent_reference: f.consent_reference || null,
      });
      setOpen(false); onCreated();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  if (!open) return <Button onClick={() => setOpen(true)}>New requirement</Button>;
  return (
    <form onSubmit={submit} className="card grid gap-4 p-5 md:grid-cols-2">
      {err && <div className="md:col-span-2"><Alert>{err}</Alert></div>}
      <Field label="Customer name"><Input required value={f.full_name} onChange={set("full_name")} /></Field>
      <Field label="Customer email"><Input required type="email" value={f.email} onChange={set("email")} /></Field>
      <Field label="Service category">
        <select required className={selectCls} value={f.category_id} onChange={set("category_id")}>
          <option value="">Select…</option>{cats.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </Field>
      <Field label="Title"><Input required value={f.title} onChange={set("title")} /></Field>
      <Field label="City"><Input value={f.city} onChange={set("city")} /></Field>
      <Field label="Country (ISO-2)"><Input maxLength={2} value={f.country} onChange={set("country")} /></Field>
      <Field label="Budget min"><Input inputMode="decimal" value={f.budget_min} onChange={set("budget_min")} /></Field>
      <Field label="Budget max"><Input inputMode="decimal" value={f.budget_max} onChange={set("budget_max")} /></Field>
      <Field label="Currency"><Input maxLength={3} value={f.currency} onChange={set("currency")} /></Field>
      <Field label="Timeline"><Input value={f.timeline} onChange={set("timeline")} placeholder="e.g. within 3 months" /></Field>
      <div className="md:col-span-2"><Field label="Description"><textarea className={areaCls} rows={3} value={f.description} onChange={set("description")} /></Field></div>
      <label className="flex items-center gap-2 text-sm md:col-span-2">
        <input type="checkbox" checked={f.contact_permission} onChange={(e) => setF({ ...f, contact_permission: e.target.checked })} />
        Customer has given permission to share their contact details with providers
      </label>
      {f.contact_permission && <Field label="Consent reference (required)"><Input required value={f.consent_reference} onChange={set("consent_reference")} placeholder="e.g. signed form ID" /></Field>}
      <div className="flex gap-2 md:col-span-2"><Button loading={busy}>Save requirement</Button><Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button></div>
    </form>
  );
}

function ProviderForm({ cats, onCreated }: { cats: Category[]; onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ business_name: "", email: "", phone: "", city: "", country: "", experience_years: "", price_min: "", price_max: "", currency: "INR", availability: "available", description: "" });
  const [catIds, setCatIds] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      await mkt.createProvider({
        business_name: f.business_name, email: f.email || null, phone: f.phone || null, description: f.description || null,
        service_areas: f.city || f.country ? [{ city: f.city || undefined, country: f.country.toUpperCase() || undefined }] : [],
        experience_years: f.experience_years ? Number(f.experience_years) : null, price_min: f.price_min || null,
        price_max: f.price_max || null, currency: f.currency, availability: f.availability, category_ids: catIds,
      });
      setOpen(false); onCreated();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  if (!open) return <Button onClick={() => setOpen(true)}>New provider</Button>;
  return (
    <form onSubmit={submit} className="card grid gap-4 p-5 md:grid-cols-2">
      {err && <div className="md:col-span-2"><Alert>{err}</Alert></div>}
      <Field label="Business name"><Input required value={f.business_name} onChange={set("business_name")} /></Field>
      <Field label="Email"><Input type="email" value={f.email} onChange={set("email")} /></Field>
      <Field label="Service city"><Input value={f.city} onChange={set("city")} /></Field>
      <Field label="Service country (ISO-2)"><Input maxLength={2} value={f.country} onChange={set("country")} /></Field>
      <Field label="Experience (years)"><Input inputMode="numeric" value={f.experience_years} onChange={set("experience_years")} /></Field>
      <Field label="Availability">
        <select className={selectCls} value={f.availability} onChange={set("availability")}>
          <option value="available">Available</option><option value="limited">Limited</option><option value="unavailable">Unavailable</option>
        </select>
      </Field>
      <Field label="Typical project min"><Input inputMode="decimal" value={f.price_min} onChange={set("price_min")} /></Field>
      <Field label="Typical project max"><Input inputMode="decimal" value={f.price_max} onChange={set("price_max")} /></Field>
      <div className="md:col-span-2">
        <span className="mb-1 block text-xs text-muted">Categories</span>
        <div className="flex flex-wrap gap-2">
          {cats.map((c) => (
            <button type="button" key={c.id} onClick={() => setCatIds(catIds.includes(c.id) ? catIds.filter((x) => x !== c.id) : [...catIds, c.id])}
              className={`rounded-full border px-3 py-1 text-sm ${catIds.includes(c.id) ? "border-accent bg-accent-soft text-accent" : "border-line"}`}>{c.name}</button>
          ))}
        </div>
      </div>
      <div className="md:col-span-2"><Field label="Description"><textarea className={areaCls} rows={3} value={f.description} onChange={set("description")} /></Field></div>
      <p className="text-xs text-muted md:col-span-2">New providers start as unverified. Verification is recorded manually with evidence on the provider page.</p>
      <div className="flex gap-2 md:col-span-2"><Button loading={busy}>Save provider</Button><Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button></div>
    </form>
  );
}
