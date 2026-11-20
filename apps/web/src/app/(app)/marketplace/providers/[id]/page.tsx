"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, FileText } from "lucide-react";
import { Alert, Button, Input } from "@/components/ui";
import { fmtMoney, label, mkt, type Doc, type Provider, type Verification } from "@/lib/marketplace";
import { InviteToPortal } from "../../_invite";
import { Field, VerificationBadge, areaCls, selectCls } from "../../_ui";

export default function ProviderPage() {
  const { id } = useParams<{ id: string }>();
  const [p, setP] = useState<Provider | null>(null);
  const [docs, setDocs] = useState<Doc[]>([]);
  const [vers, setVers] = useState<Verification[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [a, b, c] = await Promise.all([mkt.provider(id), mkt.documents(id), mkt.verifications(id)]);
      setP(a); setDocs(b); setVers(c);
    } catch (e) { setError((e as Error).message); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);

  if (!p) return error ? <Alert>{error}</Alert> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-6">
      <Link href="/marketplace" className="inline-flex items-center gap-1 text-sm text-muted hover:text-neutral-900"><ArrowLeft className="h-4 w-4" />Marketplace</Link>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{p.business_name}</h1>
          <p className="mt-1 text-sm text-muted">{p.email ?? "No email"} · {p.experience_years ?? "?"} yrs · {label(p.availability)}</p>
        </div>
        <div className="flex flex-col items-end gap-2"><VerificationBadge status={p.verification_status} /><InviteToPortal kind="provider" id={p.id} /></div>
      </div>
      {error && <Alert>{error}</Alert>}
      <section className="card grid gap-3 p-5 text-sm md:grid-cols-2">
        <div><span className="text-muted">Service areas: </span>{(p.service_areas ?? []).map((a) => [a.city, a.country].filter(Boolean).join(", ")).join("; ") || "—"}</div>
        <div><span className="text-muted">Pricing: </span>{fmtMoney(p.price_min, p.currency)} – {fmtMoney(p.price_max, p.currency)}</div>
        <div className="md:col-span-2"><span className="text-muted">About: </span>{p.description ?? "—"}</div>
        <PortalLink p={p} onSaved={load} />
      </section>
      <Documents id={id} docs={docs} onChange={load} />
      <VerifyForm id={id} docs={docs} onDone={load} />
      <section className="card">
        <h2 className="border-b border-line px-5 py-3 text-sm font-medium">Verification history</h2>
        <ul className="divide-y divide-line">
          {vers.length === 0 && <li className="px-5 py-3 text-sm text-muted">No verification recorded.</li>}
          {vers.map((v) => (
            <li key={v.id} className="px-5 py-3 text-sm">
              <div className="flex justify-between"><span><VerificationBadge status={v.decision} /> <span className="ml-2 text-muted">{v.method}{v.reference ? ` · ref ${v.reference}` : ""}</span></span><time className="text-xs text-muted">{new Date(v.created_at).toLocaleString()}</time></div>
              {v.evidence && <p className="mt-1 text-muted">{v.evidence}</p>}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function PortalLink({ p, onSaved }: { p: Provider; onSaved: () => void }) {
  const [uid, setUid] = useState(p.portal_user_id ?? "");
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    setErr(null);
    try { await mkt.updateProvider(p.id, { portal_user_id: uid || null }); onSaved(); } catch (e) { setErr((e as Error).message); }
  };
  return (
    <div className="md:col-span-2">
      <Field label="Provider portal user ID (must be an org member, e.g. Viewer role)">
        <div className="flex gap-2"><Input value={uid} onChange={(e) => setUid(e.target.value)} placeholder="user UUID" /><Button variant="outline" type="button" onClick={save}>Link</Button></div>
      </Field>
      {err && <p className="mt-1 text-xs text-danger">{err}</p>}
    </div>
  );
}

function Documents({ id, docs, onChange }: { id: string; docs: Doc[]; onChange: () => void }) {
  const [type, setType] = useState("rera");
  const [file, setFile] = useState<File | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const upload = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { setErr("Files must be 5 MB or smaller"); return; }
    setBusy(true); setErr(null);
    try { await mkt.upload(id, type, file); setFile(null); onChange(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <section className="card">
      <h2 className="border-b border-line px-5 py-3 text-sm font-medium">Documents</h2>
      <ul className="divide-y divide-line">
        {docs.map((d) => (
          <li key={d.id} className="flex items-center justify-between px-5 py-2.5 text-sm">
            <span className="flex items-center gap-2"><FileText className="h-4 w-4 text-muted" />{d.filename} <span className="text-xs text-muted">{d.document_type.toUpperCase()} · {(d.size_bytes / 1024).toFixed(0)} KB</span></span>
            <span className="font-mono text-[11px] text-muted">{d.sha256.slice(0, 12)}</span>
          </li>
        ))}
      </ul>
      <form onSubmit={upload} className="flex flex-wrap items-end gap-3 border-t border-line p-5">
        <Field label="Type">
          <select className={selectCls} value={type} onChange={(e) => setType(e.target.value)}>
            {["rera", "license", "registration", "insurance", "certificate", "portfolio", "other"].map((t) => <option key={t} value={t}>{t.toUpperCase()}</option>)}
          </select>
        </Field>
        <input type="file" accept="application/pdf,image/png,image/jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
        <Button loading={busy} disabled={!file}>Upload</Button>
        <p className="w-full text-xs text-muted">PDF, PNG or JPEG, max 5 MB.</p>
        {err && <div className="w-full"><Alert>{err}</Alert></div>}
      </form>
    </section>
  );
}

function VerifyForm({ id, docs, onDone }: { id: string; docs: Doc[]; onDone: () => void }) {
  const [decision, setDecision] = useState("verified");
  const [reference, setReference] = useState("");
  const [evidence, setEvidence] = useState("");
  const [docIds, setDocIds] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(null);
    if (!confirm(`Record a manual "${decision}" decision? This is logged with your name.`)) return;
    try {
      await mkt.verify(id, { method: "manual", decision, reference: reference || null, evidence: evidence || null, document_ids: docIds });
      setEvidence(""); setReference(""); setDocIds([]); onDone();
    } catch (e) { setErr((e as Error).message); }
  };
  return (
    <form onSubmit={submit} className="card grid gap-4 p-5 md:grid-cols-2">
      <h2 className="text-sm font-medium md:col-span-2">Record manual verification</h2>
      <p className="text-xs text-muted md:col-span-2">Automated registry checks (e.g. RERA portals) are not configured. Check the credential yourself and record what you saw.</p>
      {err && <div className="md:col-span-2"><Alert>{err}</Alert></div>}
      <Field label="Decision">
        <select className={selectCls} value={decision} onChange={(e) => setDecision(e.target.value)}>
          <option value="pending">Pending</option><option value="verified">Verified</option><option value="rejected">Rejected</option>
        </select>
      </Field>
      <Field label="Registration / license number"><Input value={reference} onChange={(e) => setReference(e.target.value)} /></Field>
      <div className="md:col-span-2"><Field label="Evidence (what was checked, where, when)"><textarea className={areaCls} rows={3} value={evidence} onChange={(e) => setEvidence(e.target.value)} /></Field></div>
      {docs.length > 0 && (
        <div className="flex flex-wrap gap-3 text-sm md:col-span-2">
          {docs.map((d) => (
            <label key={d.id} className="flex items-center gap-1.5">
              <input type="checkbox" checked={docIds.includes(d.id)} onChange={() => setDocIds(docIds.includes(d.id) ? docIds.filter((x) => x !== d.id) : [...docIds, d.id])} />{d.filename}
            </label>
          ))}
        </div>
      )}
      <div className="md:col-span-2"><Button>Record decision</Button></div>
    </form>
  );
}
