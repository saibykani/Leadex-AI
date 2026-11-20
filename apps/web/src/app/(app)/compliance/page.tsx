"use client";
import { useCallback, useEffect, useState } from "react";
import { Ban, CheckCircle2, FileCheck2, OctagonX, Power, ShieldCheck, XCircle } from "lucide-react";
import { api, type Page } from "@/lib/api";
import { useSession } from "@/lib/session-context";
import { BASES, CHANNELS, compliance, type Consent, type Dsr, type GateResult, type KillSwitch, type Suppression } from "@/lib/compliance";
import { Alert, Badge, Button, EmptyState, Input, PageHeader, Select, Skeleton, Table, Tabs, Textarea, useToast } from "@/components/ui";

type Tab = "check" | "consents" | "suppressions" | "kill" | "dsr" | "dnc";
type LeadLite = { id: string; business_name: string; country: string | null; status: string };

const fmt = (d: string | null) => (d ? new Date(d).toLocaleString() : "—");
const errMsg = (e: unknown) => (e as Error).message;

function useLeads() {
  const [leads, setLeads] = useState<LeadLite[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<Page<LeadLite>>("/leads?page_size=200&sort=business_name", {}, true).then((p) => setLeads(p.items)).catch((e) => setError(errMsg(e)));
  }, []);
  return { leads, error };
}

function LeadPicker({ value, onChange, id }: { value: string; onChange: (v: string) => void; id: string }) {
  const { leads, error } = useLeads();
  if (error) return <Alert>{error}</Alert>;
  if (!leads) return <Skeleton className="h-10 w-full" />;
  if (!leads.length) return <p className="text-sm text-muted">No leads yet. Add leads first.</p>;
  return (
    <Select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="w-full">
      <option value="">Select a lead…</option>
      {leads.map((l) => <option key={l.id} value={l.id}>{l.business_name}{l.country ? ` (${l.country})` : ""} · {l.status}</option>)}
    </Select>
  );
}

export default function CompliancePage() {
  const { can } = useSession();
  const [tab, setTab] = useState<Tab>("check");
  const tabs: { id: Tab; label: string }[] = [
    { id: "check", label: "Gate checker" }, { id: "consents", label: "Consents" }, { id: "suppressions", label: "Suppressions" },
    { id: "kill", label: "Kill switches" }, { id: "dnc", label: "DNC registry" },
    ...(can("org:write") ? [{ id: "dsr" as Tab, label: "Data requests" }] : []),
  ];
  return (
    <div className="max-w-5xl space-y-6">
      <PageHeader title="Compliance" description="Consent evidence, suppression lists, kill switches and the outreach gate every channel must pass." />
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      {tab === "check" && <GateChecker />}
      {tab === "consents" && <Consents />}
      {tab === "suppressions" && <Suppressions />}
      {tab === "kill" && <KillSwitches />}
      {tab === "dsr" && <DataRequests />}
      {tab === "dnc" && <DncRegistry />}
    </div>
  );
}

function GateChecker() {
  const [lead, setLead] = useState("");
  const [channel, setChannel] = useState<string>("email");
  const [result, setResult] = useState<GateResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null); setResult(null);
    try { setResult(await compliance.check(lead, channel)); } catch (err) { setError(errMsg(err)); } finally { setBusy(false); }
  }
  return (
    <div className="space-y-4">
      <form onSubmit={run} className="card grid gap-4 p-6 sm:grid-cols-[1fr_160px_auto] sm:items-end">
        <div><label className="label" htmlFor="g-lead">Lead</label><LeadPicker id="g-lead" value={lead} onChange={setLead} /></div>
        <div><label className="label" htmlFor="g-ch">Channel</label>
          <Select id="g-ch" value={channel} onChange={(e) => setChannel(e.target.value)} className="w-full">{CHANNELS.map((c) => <option key={c}>{c}</option>)}</Select></div>
        <Button type="submit" loading={busy} disabled={!lead} className="h-10">Check</Button>
      </form>
      {error && <Alert>{error}</Alert>}
      {result && (
        <div className="card space-y-3 p-6">
          <div className="flex flex-wrap items-center gap-2">
            {result.allowed
              ? <Badge tone="success"><CheckCircle2 className="h-3.5 w-3.5" />Allowed</Badge>
              : <Badge tone="danger"><XCircle className="h-3.5 w-3.5" />Blocked</Badge>}
            {result.simulated && <Badge tone="warning">Simulated mode — no real contact will be made</Badge>}
            <Badge>Jurisdiction: {result.jurisdiction ?? "unknown"}</Badge>
          </div>
          {result.reasons.length > 0 && (
            <ul className="space-y-1 text-sm">{result.reasons.map((r) => <li key={r} className="font-mono text-danger">{r}</li>)}</ul>
          )}
          <p className="text-xs text-muted">Calling windows use approximate standard-time offsets per jurisdiction (DST not applied); DNC registries are not queried automatically.</p>
        </div>
      )}
    </div>
  );
}

function Consents() {
  const { can } = useSession();
  const toast = useToast();
  const [data, setData] = useState<Consent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ lead_id: "", channel: "email", basis: "express_consent", evidence_text: "", evidence_url: "" });
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => compliance.consents().then((p) => setData(p.items)).catch((e) => setError(errMsg(e))), []);
  useEffect(() => { void load(); }, [load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      await compliance.createConsent({ ...form, evidence_text: form.evidence_text || undefined, evidence_url: form.evidence_url || undefined });
      setForm((f) => ({ ...f, evidence_text: "", evidence_url: "" })); toast("Consent recorded", "success"); await load();
    } catch (err) { setError(errMsg(err)); } finally { setBusy(false); }
  }
  async function withdraw(id: string) {
    try { await compliance.withdrawConsent(id, "Withdrawn via console"); toast("Consent withdrawn", "success"); await load(); }
    catch (err) { setError(errMsg(err)); }
  }
  return (
    <div className="space-y-4">
      {error && <Alert>{error}</Alert>}
      {can("leads:write") && (
        <form onSubmit={submit} className="card grid gap-4 p-6 sm:grid-cols-2">
          <h2 className="flex items-center gap-2 text-[15px] font-semibold sm:col-span-2"><FileCheck2 className="h-4 w-4 text-accent" />Record consent</h2>
          <div className="sm:col-span-2"><label className="label" htmlFor="c-lead">Lead</label><LeadPicker id="c-lead" value={form.lead_id} onChange={(v) => setForm({ ...form, lead_id: v })} /></div>
          <div><label className="label" htmlFor="c-ch">Channel</label>
            <Select id="c-ch" className="w-full" value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })}>{CHANNELS.map((c) => <option key={c}>{c}</option>)}</Select></div>
          <div><label className="label" htmlFor="c-basis">Basis</label>
            <Select id="c-basis" className="w-full" value={form.basis} onChange={(e) => setForm({ ...form, basis: e.target.value })}>{BASES.map((b) => <option key={b} value={b}>{b.replace(/_/g, " ")}</option>)}</Select></div>
          <div className="sm:col-span-2"><label className="label" htmlFor="c-ev">Evidence</label>
            <Textarea id="c-ev" rows={2} placeholder="How and when consent was given" value={form.evidence_text} onChange={(e) => setForm({ ...form, evidence_text: e.target.value })} /></div>
          <div className="sm:col-span-2"><label className="label" htmlFor="c-url">Evidence URL (optional)</label>
            <Input id="c-url" className="h-10" value={form.evidence_url} onChange={(e) => setForm({ ...form, evidence_url: e.target.value })} /></div>
          <div className="sm:col-span-2"><Button type="submit" loading={busy} disabled={!form.lead_id || (!form.evidence_text && !form.evidence_url)}>Save consent</Button></div>
        </form>
      )}
      {!data ? <Skeleton className="h-40 w-full" /> : data.length === 0 ? (
        <EmptyState icon={<ShieldCheck className="h-5 w-5" />} title="No consent records" body="Outreach is blocked for every lead until consent evidence is recorded for that channel." />
      ) : (
        <Table head={["Lead", "Channel", "Basis", "Captured", "Status", ""]}>
          {data.map((c) => (
            <tr key={c.id}>
              <td className="px-5 py-3 font-mono text-xs text-muted">{c.lead_id.slice(0, 8)}</td>
              <td className="px-5 py-3">{c.channel}</td>
              <td className="px-5 py-3">{c.basis.replace(/_/g, " ")}</td>
              <td className="px-5 py-3 text-muted">{fmt(c.captured_at)}</td>
              <td className="px-5 py-3">{c.withdrawn_at ? <Badge tone="danger">Withdrawn</Badge> : <Badge tone="success">Active</Badge>}</td>
              <td className="px-5 py-3 text-right">{!c.withdrawn_at && can("leads:write") && <Button variant="ghost" className="h-8 px-3 text-sm" onClick={() => withdraw(c.id)}>Withdraw</Button>}</td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}

function Suppressions() {
  const { can } = useSession();
  const toast = useToast();
  const [data, setData] = useState<Suppression[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ channel: "all", email: "", phone: "", reason: "" });
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => compliance.suppressions().then((p) => setData(p.items)).catch((e) => setError(errMsg(e))), []);
  useEffect(() => { void load(); }, [load]);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      await compliance.createSuppression({ channel: form.channel, reason: form.reason, email: form.email || undefined, phone: form.phone || undefined });
      setForm({ channel: "all", email: "", phone: "", reason: "" }); toast("Contact suppressed", "success"); await load();
    } catch (err) { setError(errMsg(err)); } finally { setBusy(false); }
  }
  async function remove(id: string) {
    try { await compliance.deleteSuppression(id); toast("Suppression removed", "success"); await load(); } catch (err) { setError(errMsg(err)); }
  }
  return (
    <div className="space-y-4">
      {error && <Alert>{error}</Alert>}
      {can("leads:write") && (
        <form onSubmit={submit} className="card grid gap-4 p-6 sm:grid-cols-4 sm:items-end">
          <div><label className="label" htmlFor="s-ch">Channel</label>
            <Select id="s-ch" className="w-full" value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })}>{["all", ...CHANNELS].map((c) => <option key={c}>{c}</option>)}</Select></div>
          <div><label className="label" htmlFor="s-em">Email</label><Input id="s-em" className="h-10" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
          <div><label className="label" htmlFor="s-ph">Phone</label><Input id="s-ph" className="h-10" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></div>
          <div><label className="label" htmlFor="s-r">Reason</label><Input id="s-r" className="h-10" required value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></div>
          <div className="sm:col-span-4"><Button type="submit" loading={busy} disabled={!form.reason || (!form.email && !form.phone)}><Ban className="h-4 w-4" />Suppress</Button></div>
        </form>
      )}
      {!data ? <Skeleton className="h-40 w-full" /> : data.length === 0 ? (
        <EmptyState icon={<Ban className="h-5 w-5" />} title="No suppressions" body="Suppressed emails and phone numbers are never contacted on the chosen channel." />
      ) : (
        <Table head={["Contact", "Channel", "Reason", "Added", ""]}>
          {data.map((s) => (
            <tr key={s.id}>
              <td className="px-5 py-3">{s.email_normalized ?? ""}{s.email_normalized && s.phone_normalized ? " · " : ""}{s.phone_normalized ?? ""}</td>
              <td className="px-5 py-3">{s.channel}</td>
              <td className="px-5 py-3 text-muted">{s.reason}</td>
              <td className="px-5 py-3 text-muted">{fmt(s.created_at)}</td>
              <td className="px-5 py-3 text-right">{can("org:write") && <Button variant="ghost" className="h-8 px-3 text-sm" onClick={() => remove(s.id)}>Remove</Button>}</td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}

function KillSwitches() {
  const { current } = useSession();
  const toast = useToast();
  const admin = current.role === "Owner" || current.role === "Admin";
  const [data, setData] = useState<KillSwitch[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [channel, setChannel] = useState("all");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => compliance.killSwitches().then(setData).catch((e) => setError(errMsg(e))), []);
  useEffect(() => { void load(); }, [load]);
  async function activate(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try { await compliance.createKillSwitch({ channel, reason }); setReason(""); toast("Kill switch activated", "success"); await load(); }
    catch (err) { setError(errMsg(err)); } finally { setBusy(false); }
  }
  async function deactivate(id: string) {
    try { await compliance.deactivateKillSwitch(id); toast("Kill switch released", "success"); await load(); } catch (err) { setError(errMsg(err)); }
  }
  return (
    <div className="space-y-4">
      {error && <Alert>{error}</Alert>}
      {admin ? (
        <form onSubmit={activate} className="card grid gap-4 p-6 sm:grid-cols-[160px_1fr_auto] sm:items-end">
          <div><label className="label" htmlFor="k-ch">Channel</label>
            <Select id="k-ch" className="w-full" value={channel} onChange={(e) => setChannel(e.target.value)}>{["all", ...CHANNELS].map((c) => <option key={c}>{c}</option>)}</Select></div>
          <div><label className="label" htmlFor="k-r">Reason</label><Input id="k-r" className="h-10" required value={reason} onChange={(e) => setReason(e.target.value)} /></div>
          <Button type="submit" loading={busy} disabled={!reason} className="h-10 bg-danger hover:bg-danger/90"><OctagonX className="h-4 w-4" />Stop outreach</Button>
        </form>
      ) : <p className="text-sm text-muted">Only Owners and Admins can activate kill switches.</p>}
      {!data ? <Skeleton className="h-32 w-full" /> : data.length === 0 ? (
        <EmptyState icon={<Power className="h-5 w-5" />} title="No kill switches" body="Activate a kill switch to immediately block all outreach on a channel for this organization." />
      ) : (
        <Table head={["Scope", "Channel", "Reason", "Since", "State", ""]}>
          {data.map((k) => (
            <tr key={k.id}>
              <td className="px-5 py-3"><Badge tone={k.scope === "global" ? "violet" : "neutral"}>{k.scope}</Badge></td>
              <td className="px-5 py-3">{k.channel}</td>
              <td className="px-5 py-3 text-muted">{k.reason}</td>
              <td className="px-5 py-3 text-muted">{fmt(k.created_at)}</td>
              <td className="px-5 py-3">{k.active ? <Badge tone="danger">Active</Badge> : <Badge>Released</Badge>}</td>
              <td className="px-5 py-3 text-right">{k.active && admin && k.scope === "organization" && <Button variant="ghost" className="h-8 px-3 text-sm" onClick={() => deactivate(k.id)}>Release</Button>}</td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}

const DSR_TYPES = ["access", "correction", "deletion", "export", "withdrawal"];
function DataRequests() {
  const toast = useToast();
  const [data, setData] = useState<Dsr[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ type: "access", subject_email: "", subject_phone: "", details: "" });
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => compliance.dsrs().then((p) => setData(p.items)).catch((e) => setError(errMsg(e))), []);
  useEffect(() => { void load(); }, [load]);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      await compliance.createDsr({ type: form.type, subject_email: form.subject_email || undefined, subject_phone: form.subject_phone || undefined, details: form.details || undefined });
      setForm({ type: "access", subject_email: "", subject_phone: "", details: "" }); toast("Request logged", "success"); await load();
    } catch (err) { setError(errMsg(err)); } finally { setBusy(false); }
  }
  async function exportData(d: Dsr) {
    try {
      const bundle = await api<{ records: unknown[] }>(`/compliance/dsr/${d.id}/export`, { method: "POST" }, true);
      const url = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" }));
      const a = document.createElement("a"); a.href = url; a.download = `data-request-${d.id}.json`; a.click(); URL.revokeObjectURL(url);
      toast(`Exported ${bundle.records.length} record set(s)`, "success"); await load();
    } catch (err) { setError(errMsg(err)); }
  }
  async function eraseData(d: Dsr) {
    if (!window.confirm("Permanently erase this person's personal data? Transcripts, notes and messages are deleted; a do-not-contact entry is kept. This cannot be undone.")) return;
    try { await api(`/compliance/dsr/${d.id}/erase`, { method: "POST" }, true); toast("Personal data erased and request completed", "success"); await load(); }
    catch (err) { setError(errMsg(err)); }
  }
  async function setStatus(d: Dsr, status: string) {
    let resolution: string | undefined;
    if (status === "completed" || status === "rejected") {
      resolution = window.prompt("Resolution note (required)") ?? undefined;
      if (!resolution) return;
    }
    try { await compliance.updateDsr(d.id, status, resolution); await load(); } catch (err) { setError(errMsg(err)); }
  }
  return (
    <div className="space-y-4">
      {error && <Alert>{error}</Alert>}
      <form onSubmit={submit} className="card grid gap-4 p-6 sm:grid-cols-3 sm:items-end">
        <div><label className="label" htmlFor="d-t">Type</label>
          <Select id="d-t" className="w-full" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>{DSR_TYPES.map((t) => <option key={t}>{t}</option>)}</Select></div>
        <div><label className="label" htmlFor="d-e">Subject email</label><Input id="d-e" className="h-10" value={form.subject_email} onChange={(e) => setForm({ ...form, subject_email: e.target.value })} /></div>
        <div><label className="label" htmlFor="d-p">Subject phone</label><Input id="d-p" className="h-10" value={form.subject_phone} onChange={(e) => setForm({ ...form, subject_phone: e.target.value })} /></div>
        <div className="sm:col-span-3"><label className="label" htmlFor="d-d">Details</label><Textarea id="d-d" rows={2} value={form.details} onChange={(e) => setForm({ ...form, details: e.target.value })} /></div>
        <div className="sm:col-span-3"><Button type="submit" loading={busy} disabled={!form.subject_email && !form.subject_phone}>Log request</Button></div>
      </form>
      {!data ? <Skeleton className="h-32 w-full" /> : data.length === 0 ? (
        <EmptyState icon={<FileCheck2 className="h-5 w-5" />} title="No data subject requests" body="Access, deletion and other privacy requests are tracked here with a 30-day due date." />
      ) : (
        <Table head={["Type", "Subject", "Due", "Status", ""]}>
          {data.map((d) => {
            const open = d.status === "open" || d.status === "in_progress";
            return (
              <tr key={d.id}>
                <td className="px-5 py-3">{d.type}</td>
                <td className="px-5 py-3 text-muted">{d.subject_email ?? d.subject_phone ?? d.lead_id}</td>
                <td className="px-5 py-3 text-muted">{fmt(d.due_at)}</td>
                <td className="px-5 py-3"><Badge tone={d.status === "completed" ? "success" : d.status === "rejected" ? "danger" : "warning"}>{d.status.replace("_", " ")}</Badge></td>
                <td className="space-x-1 px-5 py-3 text-right">
                  <Button variant="ghost" className="h-8 px-3 text-sm" onClick={() => exportData(d)}>Export data</Button>
                  {open && d.type === "deletion" && <Button variant="ghost" className="h-8 px-3 text-sm text-danger" onClick={() => eraseData(d)}>Erase data</Button>}
                  {d.status === "open" && <Button variant="ghost" className="h-8 px-3 text-sm" onClick={() => setStatus(d, "in_progress")}>Start</Button>}
                  {open && <Button variant="ghost" className="h-8 px-3 text-sm" onClick={() => setStatus(d, "completed")}>Complete</Button>}
                  {open && <Button variant="ghost" className="h-8 px-3 text-sm" onClick={() => setStatus(d, "rejected")}>Reject</Button>}
                </td>
              </tr>
            );
          })}
        </Table>
      )}
    </div>
  );
}

type DncStatus = { enforced: boolean; max_age_days: number; api_configured: boolean;
  countries: { country: string; registry: string; entries: number; last_import_at: string | null; fresh: boolean }[] };

function DncRegistry() {
  const { can } = useSession();
  const toast = useToast();
  const [st, setSt] = useState<DncStatus | null>(null);
  const [country, setCountry] = useState("IN");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<DncStatus>("/compliance/dnc/status", {}, true).then(setSt).catch((e) => setError(errMsg(e))), []);
  useEffect(() => { void load(); }, [load]);
  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true); setError(null);
    try {
      const fd = new FormData(); fd.append("country", country); fd.append("file", file);
      const r = await api<{ imported: number; rejected: number }>("/compliance/dnc/import", { method: "POST", body: fd }, true);
      toast(`Imported ${r.imported} numbers${r.rejected ? `, ${r.rejected} unreadable lines skipped` : ""}`, "success"); setFile(null); await load();
    } catch (err) { setError(errMsg(err)); } finally { setBusy(false); }
  }
  return (
    <div className="space-y-4">
      {error && <Alert>{error}</Alert>}
      <div className="card space-y-2 p-6 text-sm">
        <p>Numbers on a national do-not-call registry are blocked for calls, SMS and WhatsApp.
          Import the scrub file from your own registry subscription (for India: TRAI NCPR via your DLT/telemarketer registration).</p>
        {st && <p className="text-muted">Enforcement: <b>{st.enforced ? "on — calls are blocked until the registry was checked" : "off (development)"}</b> ·
          files older than {st.max_age_days} days count as stale{st.api_configured ? " · registry API connected" : ""}.</p>}
      </div>
      {!st ? <Skeleton className="h-40 w-full" /> : (
        <Table head={["Country", "Registry", "Numbers", "Last import", "Status"]}>
          {st.countries.map((c) => (
            <tr key={c.country}>
              <td className="px-5 py-3 font-medium">{c.country}</td>
              <td className="px-5 py-3 text-muted">{c.registry}</td>
              <td className="px-5 py-3">{c.entries.toLocaleString()}</td>
              <td className="px-5 py-3 text-muted">{fmt(c.last_import_at)}</td>
              <td className="px-5 py-3">{c.last_import_at ? <Badge tone={c.fresh ? "success" : "warning"}>{c.fresh ? "up to date" : "stale"}</Badge> : <Badge>not imported</Badge>}</td>
            </tr>
          ))}
        </Table>
      )}
      {can("org:write") && (
        <form onSubmit={upload} className="card flex flex-wrap items-end gap-3 p-6">
          <div><label className="label" htmlFor="dnc-c">Country</label>
            <Select id="dnc-c" value={country} onChange={(e) => setCountry(e.target.value)}>{(st?.countries ?? []).map((c) => <option key={c.country} value={c.country}>{c.country} · {c.registry}</option>)}</Select></div>
          <div className="min-w-60 flex-1"><label className="label" htmlFor="dnc-f">Registry file (CSV/TXT, one number per line or a “phone” column)</label>
            <input id="dnc-f" type="file" accept=".csv,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="block w-full text-sm" /></div>
          <Button type="submit" loading={busy} disabled={!file}>Import (replaces previous list)</Button>
        </form>
      )}
    </div>
  );
}
