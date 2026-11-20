"use client";
import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Download, FlaskConical, Search, Upload } from "lucide-react";
import { Alert, Button, EmptyState, Input } from "@/components/ui";
import { useSession } from "@/lib/session-context";
import type { Page } from "@/lib/api";
import {
  discovery, WEBSITE_STATUSES, websiteStatusLabel,
  type Business, type Criteria, type SearchJob, type Sources,
} from "@/lib/discovery";
import { StatusBadge } from "./status-badge";

const FIELDS: { key: keyof Criteria; label: string; placeholder?: string }[] = [
  { key: "industry", label: "Industry", placeholder: "dental" },
  { key: "category", label: "Category", placeholder: "dentist" },
  { key: "name", label: "Business name" },
  { key: "country", label: "Country (ISO-2)", placeholder: "IN" },
  { key: "state", label: "State" },
  { key: "city", label: "City", placeholder: "Pune" },
  { key: "locality", label: "Locality" },
  { key: "postal_code", label: "Postal code" },
];

export default function DiscoveryPage() {
  const { can, current } = useSession();
  const [sources, setSources] = useState<Sources | null>(null);
  const [jobs, setJobs] = useState<Page<SearchJob> | null>(null);
  const [results, setResults] = useState<Page<Business> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [criteria, setCriteria] = useState<Criteria>({ source: "" });
  const [running, setRunning] = useState(false);
  const [filters, setFilters] = useState<{ q?: string; website_status?: string; job_id?: string; page: number }>({ page: 1 });
  const [busy, setBusy] = useState<string | null>(null);

  const loadMeta = useCallback(() => {
    discovery.sources().then((s) => {
      setSources(s);
      setCriteria((c) => c.source ? c : { ...c, source: s.sources.find((x) => x.supports_search && x.status === "configured")?.source ?? "" });
    }).catch((e) => setError(e.message));
    discovery.jobs().then(setJobs).catch((e) => setError(e.message));
  }, []);

  const loadResults = useCallback(() => {
    setResults(null);
    discovery.businesses(filters).then(setResults).catch((e) => setError(e.message));
  }, [filters]);

  useEffect(() => { setError(null); loadMeta(); }, [loadMeta, current.organization.id]);
  useEffect(() => { loadResults(); }, [loadResults, current.organization.id]);

  const selected = sources?.sources.find((s) => s.source === criteria.source);

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    setError(null); setNotice(null); setRunning(true);
    try {
      const body: Criteria = { ...criteria };
      (Object.keys(body) as (keyof Criteria)[]).forEach((k) => { if (body[k] === "" || body[k] === undefined) delete body[k]; });
      const job = await discovery.search(body);
      if (job.status === "failed") setError(`Search failed: ${job.error}`);
      else setNotice(`${job.results_count} results (${job.new_count} new, ${job.duplicate_count} already known).`);
      setFilters({ page: 1, job_id: job.id });
      loadMeta();
    } catch (err) {
      setError((err as Error).message);
    } finally { setRunning(false); }
  }

  async function onImport(file: File | undefined) {
    if (!file) return;
    setError(null); setNotice(null); setBusy("import");
    try {
      const job = await discovery.importCsv(file);
      if (job.status === "failed") setError(`Import failed: ${job.error}`);
      else setNotice(`Imported ${job.results_count} rows (${job.new_count} new, ${job.duplicate_count} merged).`);
      setFilters({ page: 1, job_id: job.id });
      loadMeta();
    } catch (err) { setError((err as Error).message); } finally { setBusy(null); }
  }

  async function onConvert(b: Business) {
    setBusy(b.id); setError(null); setNotice(null);
    try {
      await discovery.convert(b.id);
      setNotice(`"${b.name}" added to leads as 'discovered'.`);
      loadResults();
    } catch (err) { setError((err as Error).message); } finally { setBusy(null); }
  }

  const canRun = can("discovery:run");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Discovery</h1>
          <p className="mt-1 text-sm text-muted">Find businesses through official data sources or your own imports. Every field keeps its source.</p>
        </div>
        {sources && <p className="text-xs text-muted">Provider requests today: {sources.requests_used_today} / {sources.daily_request_budget}</p>}
      </div>
      {error && <Alert>{error}</Alert>}
      {notice && <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</div>}

      <section className="card p-5">
        <h2 className="mb-3 text-sm font-medium">Sources</h2>
        {!sources ? <p className="text-sm text-muted">Loading sources…</p> : (
          <div className="grid gap-3 sm:grid-cols-3">
            {sources.sources.map((s) => (
              <div key={s.source} className="rounded-xl border border-line p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">{s.label}</span><StatusBadge status={s.status} />
                </div>
                {s.detail && <p className="mt-1 text-xs text-muted">{s.detail}</p>}
              </div>
            ))}
          </div>
        )}
      </section>

      {canRun ? (
        <form onSubmit={onSearch} className="card space-y-4 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-sm font-medium">New search</h2>
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-accent">
              <Upload className="h-4 w-4" />{busy === "import" ? "Importing…" : "Import CSV"}
              <input type="file" accept=".csv,text/csv" className="hidden" disabled={busy === "import"}
                onChange={(e) => { onImport(e.target.files?.[0]); e.target.value = ""; }} />
            </label>
          </div>
          <div>
            <label className="label" htmlFor="source">Source</label>
            <select id="source" value={criteria.source} onChange={(e) => setCriteria({ ...criteria, source: e.target.value })}
              className="h-12 w-full rounded-xl border border-line bg-white px-4 text-[15px] outline-none focus:border-accent">
              <option value="">Select a source…</option>
              {sources?.sources.filter((s) => s.supports_search).map((s) => (
                <option key={s.source} value={s.source} disabled={s.status === "not_configured"}>
                  {s.label}{s.status === "not_configured" ? " — not configured" : ""}
                </option>
              ))}
            </select>
            {selected?.simulated && (
              <p className="mt-2 flex items-center gap-1.5 text-xs text-amber-700"><FlaskConical className="h-3.5 w-3.5" />
                Simulated mode creates clearly fake records ("Simulated Business N"). They are not real businesses.</p>
            )}
          </div>
          <div className="grid gap-3 sm:grid-cols-4">
            {FIELDS.map((f) => (
              <div key={f.key}>
                <label className="label" htmlFor={f.key}>{f.label}</label>
                <Input id={f.key} placeholder={f.placeholder} value={(criteria[f.key] as string) ?? ""}
                  maxLength={f.key === "country" ? 2 : 200}
                  onChange={(e) => setCriteria({ ...criteria, [f.key]: e.target.value })} />
              </div>
            ))}
            <div>
              <label className="label" htmlFor="ws">Website status</label>
              <select id="ws" value={criteria.website_status ?? ""} onChange={(e) => setCriteria({ ...criteria, website_status: e.target.value || undefined })}
                className="h-12 w-full rounded-xl border border-line bg-white px-4 text-[15px] outline-none focus:border-accent">
                <option value="">Any</option>
                {WEBSITE_STATUSES.map((s) => <option key={s} value={s}>{websiteStatusLabel[s]}</option>)}
              </select>
            </div>
          </div>
          <Button type="submit" loading={running} disabled={!criteria.source}><Search className="h-4 w-4" />Run search</Button>
        </form>
      ) : (
        <p className="text-sm text-muted">You can browse businesses, but running searches requires the discovery:run permission.</p>
      )}

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-medium">Businesses{filters.job_id && <span className="ml-2 text-xs text-muted">(latest job — <button className="text-accent" onClick={() => setFilters({ page: 1 })}>show all</button>)</span>}</h2>
          <div className="flex flex-wrap items-center gap-2">
            <Input placeholder="Search name, city, domain" className="h-9 w-full sm:w-56" value={filters.q ?? ""}
              onChange={(e) => setFilters({ ...filters, q: e.target.value, page: 1 })} />
            <select value={filters.website_status ?? ""} onChange={(e) => setFilters({ ...filters, website_status: e.target.value || undefined, page: 1 })}
              className="h-9 rounded-lg border border-line bg-white px-2 text-sm">
              <option value="">Any website status</option>
              {WEBSITE_STATUSES.map((s) => <option key={s} value={s}>{websiteStatusLabel[s]}</option>)}
            </select>
            <Button variant="outline" className="h-9 px-4 text-sm" loading={busy === "export"} onClick={async () => {
              setBusy("export");
              try { await discovery.exportCsv({ q: filters.q, website_status: filters.website_status }); }
              catch (e) { setError((e as Error).message); } finally { setBusy(null); }
            }}><Download className="h-4 w-4" />Export CSV</Button>
          </div>
        </div>
        <p className="text-xs text-muted">Exports omit Google-provided fields (except place ID) as required by Google Maps Platform terms.</p>
        {!results ? <p className="text-sm text-muted">Loading businesses…</p> : results.items.length === 0 ? (
          <EmptyState icon={<Search className="h-5 w-5" />} title="No businesses yet"
            body="Run a search with a configured source or import a CSV of your own business data." />
        ) : (
          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-left text-xs text-muted">
                <tr><th className="px-4 py-2">Name</th><th className="px-4 py-2">Category</th><th className="px-4 py-2">City</th>
                  <th className="px-4 py-2">Website</th><th className="px-4 py-2">Source</th><th className="px-4 py-2" /></tr>
              </thead>
              <tbody>
                {results.items.map((b) => (
                  <tr key={b.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-2">
                      <Link href={`/businesses/${b.id}`} className="font-medium hover:text-accent">{b.name ?? <span className="italic text-muted">expired provider data</span>}</Link>
                      {b.is_simulated && <span className="ml-2 rounded bg-amber-100 px-1.5 text-[10px] font-semibold uppercase text-amber-800">simulated</span>}
                    </td>
                    <td className="px-4 py-2 text-muted">{b.category ?? b.industry ?? "—"}</td>
                    <td className="px-4 py-2 text-muted">{b.city ?? "—"}</td>
                    <td className="px-4 py-2"><StatusBadge status={b.website_status} /></td>
                    <td className="px-4 py-2 text-muted">{b.source}</td>
                    <td className="px-4 py-2 text-right">
                      {b.lead_id ? <span className="text-xs text-muted">In leads</span> : can("businesses:write") && can("leads:write") ? (
                        <Button variant="outline" className="h-8 px-3 text-xs" loading={busy === b.id} onClick={() => onConvert(b)}>Convert to lead</Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center justify-between px-4 py-2 text-xs text-muted">
              <span>{results.total} total</span>
              <div className="flex gap-2">
                <button disabled={filters.page <= 1} onClick={() => setFilters({ ...filters, page: filters.page - 1 })} className="disabled:opacity-40">Previous</button>
                <button disabled={filters.page * results.page_size >= results.total} onClick={() => setFilters({ ...filters, page: filters.page + 1 })} className="disabled:opacity-40">Next</button>
              </div>
            </div>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium">Job history</h2>
        {!jobs ? <p className="text-sm text-muted">Loading jobs…</p> : jobs.items.length === 0 ? (
          <p className="text-sm text-muted">No searches have been run yet.</p>
        ) : (
          <div className="card divide-y divide-line">
            {jobs.items.map((j) => (
              <button key={j.id} onClick={() => setFilters({ page: 1, job_id: j.id })} className="flex w-full flex-wrap items-center justify-between gap-x-3 gap-y-1 px-4 py-2.5 text-left text-sm hover:bg-raised">
                <span className="flex min-w-0 flex-wrap items-center gap-2">
                  <StatusBadge status={j.status} /><span className="font-medium">{j.source}</span>
                  <span className="min-w-0 break-all text-muted">{[j.criteria.industry, j.criteria.city, j.criteria.country].filter(Boolean).join(" · ") || String(j.criteria.filename ?? "")}</span>
                </span>
                <span className="text-xs text-muted">{j.status === "failed" ? j.error : `${j.results_count} results · ${j.cost_units} requests`} · {new Date(j.created_at).toLocaleString()}</span>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
