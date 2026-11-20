"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2, Gauge, XCircle } from "lucide-react";
import { Alert, Button, EmptyState } from "@/components/ui";
import { useSession } from "@/lib/session-context";
import { discovery, websiteStatusLabel, type BusinessDetail } from "@/lib/discovery";
import { StatusBadge } from "../../discovery/status-badge";
import { BusinessImages, GooglePhotos } from "@/components/pipeline-ui";

const fmt = (d: string | null) => (d ? new Date(d).toLocaleString() : "—");

export default function BusinessPage() {
  const { id } = useParams<{ id: string }>();
  const { can, current } = useSession();
  const [data, setData] = useState<BusinessDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ text: string; warn?: boolean } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    discovery.business(id).then(setData).catch((e) => setError(e.message));
  }, [id]);
  useEffect(() => { setData(null); load(); }, [load, current.organization.id]);

  async function act(kind: "audit" | "convert") {
    setBusy(kind); setError(null); setNotice(null);
    try {
      if (kind === "audit") {
        const a = await discovery.audit(id);
        setNotice(a.score === null ? { text: "The website could not be reached; it is marked for retry, not as 'no website'.", warn: true } : { text: `Audit complete: score ${a.score}/100.` });
      } else {
        await discovery.convert(id);
        setNotice({ text: "Added to leads with status 'discovered'." });
      }
      load();
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <Link href="/discovery" className="inline-flex items-center gap-1 text-sm text-muted hover:text-neutral-900"><ArrowLeft className="h-4 w-4" />Discovery</Link>
        {error ? <Alert>{error}</Alert> : <p className="text-sm text-muted">Loading business…</p>}
      </div>
    );
  }
  const b = data.business;
  const audit = data.audits[0];
  const rows: [string, string | number | null][] = [
    ["Industry", b.industry], ["Category", b.category], ["Address", b.address],
    ["City", [b.locality, b.city, b.state, b.postal_code, b.country].filter(Boolean).join(", ") || null],
    ["Phone", b.phone], ["Email", b.email], ["Website", b.website], ["Google place ID", b.google_place_id],
    ["Verification", b.verification_status], ["Contact permission", b.contact_permission_status],
    ["Collected", fmt(b.collected_at)], ["Last verified", fmt(b.last_verified_at)],
  ];

  return (
    <div className="space-y-6">
      <Link href="/discovery" className="inline-flex items-center gap-1 text-sm text-muted hover:text-neutral-900"><ArrowLeft className="h-4 w-4" />Discovery</Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{b.name ?? "Name unavailable (provider data expired)"}
            {b.is_simulated && <span className="ml-2 rounded bg-amber-100 px-1.5 align-middle text-[11px] font-semibold uppercase text-amber-800">simulated</span>}
          </h1>
          <p className="mt-1 flex items-center gap-2 text-sm text-muted">Source: {b.source} · Website: <StatusBadge status={b.website_status} /></p>
        </div>
        <div className="flex gap-2">
          {can("businesses:write") && b.website && !b.is_simulated && (
            <Button variant="outline" loading={busy === "audit"} onClick={() => act("audit")}><Gauge className="h-4 w-4" />Run audit</Button>
          )}
          {b.lead_id ? <Link href={`/leads/${b.lead_id}`} className="self-center text-sm text-accent hover:underline">Already in leads · Open lead</Link> :
            can("businesses:write") && can("leads:write") && <Button loading={busy === "convert"} onClick={() => act("convert")}>Convert to lead</Button>}
        </div>
      </div>
      {error && <Alert>{error}</Alert>}
      {notice && <div className={notice.warn ? "rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800" : "rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700"}>{notice.text}</div>}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card space-y-5 p-5 lg:col-span-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-medium">Gallery</h2>
            <Link href={`/pipeline?business=${id}`} className="text-sm text-accent">Open in pipeline →</Link>
          </div>
          <div><h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Google Maps photos</h3><GooglePhotos businessId={id} /></div>
          <div><h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Business images (usable in websites with permission)</h3>
            <BusinessImages businessId={id} hasWebsite={!!b.website && !b.is_simulated} /></div>
        </section>
        <section className="card p-5">
          <h2 className="mb-3 text-sm font-medium">Details</h2>
          <dl className="grid grid-cols-3 gap-y-2 text-sm">
            {rows.map(([k, v]) => (
              <div key={k} className="contents"><dt className="text-muted">{k}</dt><dd className="col-span-2 break-words">{v || "—"}</dd></div>
            ))}
          </dl>
        </section>

        <section className="card p-5">
          <h2 className="mb-3 text-sm font-medium">Website audit</h2>
          {!audit ? (
            <EmptyState icon={<Gauge className="h-5 w-5" />} title="No audit yet"
              body={b.website ? "Run an audit to check reachability, HTTPS, mobile readiness, contact info and calls to action." : `No website on record (${websiteStatusLabel[b.website_status] ?? b.website_status}).`} />
          ) : (
            <div className="space-y-3">
              <div className="flex items-baseline gap-3">
                <span className="text-4xl font-semibold">{audit.score ?? "—"}</span><span className="text-sm text-muted">/ 100</span>
                <span className="ml-auto text-xs text-muted">{fmt(audit.created_at)} · {audit.attempts} attempt(s){audit.load_ms != null && ` · ${audit.load_ms} ms`}</span>
              </div>
              {audit.error && <p className="text-xs text-amber-700">{audit.error}</p>}
              <ul className="space-y-2">
                {(audit.findings ?? []).map((f) => (
                  <li key={f.check} className="flex gap-2 text-sm">
                    {f.passed ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />}
                    <span className="flex-1">{f.explanation}</span>
                    <span className="text-xs text-muted">{f.points}{f.max_points ? `/${f.max_points}` : ""}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>

      <section className="card overflow-x-auto">
        <h2 className="px-5 pt-5 text-sm font-medium">Field provenance</h2>
        <p className="px-5 pb-3 text-xs text-muted">Where every value came from. Google Places content is retained only until its retention date; the place ID is kept.</p>
        {data.provenance.length === 0 ? <p className="px-5 pb-5 text-sm text-muted">No provenance recorded.</p> : (
          <table className="w-full text-sm">
            <thead className="border-y border-line text-left text-xs text-muted">
              <tr><th className="px-5 py-2">Field</th><th className="px-5 py-2">Value</th><th className="px-5 py-2">Source</th><th className="px-5 py-2">Reference</th><th className="px-5 py-2">Collected</th><th className="px-5 py-2">Retain until</th></tr>
            </thead>
            <tbody>
              {data.provenance.map((p) => (
                <tr key={p.id} className="border-b border-line last:border-0">
                  <td className="px-5 py-2 font-medium">{p.field}</td>
                  <td className="max-w-xs truncate px-5 py-2">{p.purged_at ? <span className="italic text-muted">purged {fmt(p.purged_at)}</span> : p.value}</td>
                  <td className="px-5 py-2 text-muted">{p.source}</td>
                  <td className="max-w-[12rem] truncate px-5 py-2 text-muted">{p.source_ref ?? "—"}</td>
                  <td className="px-5 py-2 text-muted">{fmt(p.collected_at)}</td>
                  <td className="px-5 py-2 text-muted">{p.retention_until ? fmt(p.retention_until) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
