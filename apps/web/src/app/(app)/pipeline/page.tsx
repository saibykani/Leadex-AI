"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { Bot, CheckCircle2, CircleDashed, ExternalLink, Phone, Play, Search, ShieldAlert, XCircle } from "lucide-react";
import { Alert, Badge, Button, Input, PageHeader, Select } from "@/components/ui";
import { BusinessImages, GooglePhotos, OutcomeCard } from "@/components/pipeline-ui";
import { API_URL } from "@/lib/api";
import { agentsApi, type Agent } from "@/lib/agents";
import { discovery, type Business } from "@/lib/discovery";
import { pipelineApi, type Package, type Run, type Step } from "@/lib/pipeline";
import { websites, type Template } from "@/lib/websites";

const STEP_LABEL: Record<Step["key"], string> = {
  business: "Business", photos: "Photos reviewed", lead: "Convert to lead", website: "Website demo", agent: "Agent", call: "Call",
};
const TONE = { done: "success", skipped: "neutral", blocked: "warning", failed: "danger", not_requested: "neutral" } as const;

export default function PipelinePage() {
  return <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}><Pipeline /></Suspense>;
}

function Pipeline() {
  const params = useSearchParams();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Business[]>([]);
  const [biz, setBiz] = useState<Business | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [template, setTemplate] = useState("general_smb");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentId, setAgentId] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadAgents = useCallback(() => agentsApi.list().then((p) => setAgents(p.items)).catch(() => setAgents([])), []);
  useEffect(() => {
    websites.templates().then(setTemplates).catch(() => {});
    loadAgents();
  }, [loadAgents]);
  useEffect(() => {
    const id = params.get("business");
    if (id) discovery.business(id).then((d) => setBiz(d.business)).catch((e) => setError(e.message));
  }, [params]);
  useEffect(() => {
    setRun(null); setSelected([]);
    if (biz) pipelineApi.runs(biz.id).then((r) => setRun(r[0] ?? null)).catch(() => {});
  }, [biz]);

  async function find(e?: React.FormEvent) {
    e?.preventDefault(); setError(null);
    try { setResults((await discovery.businesses({ q: q || undefined })).items); } catch (err) { setError((err as Error).message); }
  }
  useEffect(() => { find(); /* initial list */ // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function go(placeCall: boolean) {
    if (!biz) return;
    setBusy(placeCall ? "call" : "run"); setError(null);
    try {
      setRun(await pipelineApi.run({ business_id: biz.id, template_key: template, image_ids: selected, generate_website: true,
        agent_id: agentId || undefined, place_call: placeCall }));
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  }
  async function budgetAgent() {
    setBusy("agent"); setError(null);
    try { const a = await pipelineApi.budgetAgent(); await loadAgents(); setAgentId(a.id); }
    catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  }

  const leadId = run?.lead_id;
  return (
    <div className="max-w-5xl space-y-6">
      <PageHeader title="Lead pipeline" description="Business → photos → lead → website demo → AI agent conversation → outcome & budget. Every step shows its real status." />
      {error && <Alert>{error}</Alert>}

      <section className="card space-y-3 p-5">
        <h2 className="font-medium">1. Pick a business</h2>
        <form onSubmit={find} className="flex gap-2">
          <Input aria-label="Search businesses" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search discovered businesses by name…" />
          <Button type="submit" variant="outline"><Search className="h-4 w-4" />Search</Button>
        </form>
        <p className="text-xs text-muted">Need new businesses? Run a search in <Link href="/discovery" className="text-accent">Discovery</Link> (Google Places requires your GOOGLE_PLACES_API_KEY).</p>
        <div className="max-h-56 divide-y divide-line overflow-auto rounded-xl border border-line">
          {results.length === 0 && <p className="p-3 text-sm text-muted">No businesses found.</p>}
          {results.map((b) => (
            <button key={b.id} onClick={() => setBiz(b)} className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-raised ${biz?.id === b.id ? "bg-raised" : ""}`}>
              <span><b>{b.name ?? "(name expired)"}</b> <span className="text-muted">{[b.category, b.city].filter(Boolean).join(" · ")}</span></span>
              <span className="flex gap-1">{b.is_simulated && <Badge tone="warning">simulated</Badge>}<Badge>{b.source}</Badge></span>
            </button>
          ))}
        </div>
      </section>

      {biz && (
        <>
          <section className="card space-y-5 p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-medium">2. Review photos · {biz.name}</h2>
              <Link href={`/businesses/${biz.id}`} className="text-sm text-accent">Business details →</Link>
            </div>
            <div><h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Google Maps photos (review only)</h3><GooglePhotos businessId={biz.id} /></div>
            <div><h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Business images — tick “Use in website”</h3>
              <BusinessImages businessId={biz.id} hasWebsite={!!biz.website && !biz.is_simulated} selected={selected} onSelectedChange={setSelected} /></div>
          </section>

          <section className="card space-y-4 p-5">
            <h2 className="font-medium">3. Website & agent</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div><label className="label" htmlFor="tpl">Website template</label>
                <Select id="tpl" value={template} onChange={(e) => setTemplate(e.target.value)}>
                  {templates.map((t) => <option key={t.key} value={t.key}>{t.name} ({t.industry})</option>)}
                </Select>
                <p className="mt-1 text-xs text-muted">{selected.length ? `${selected.length} approved image(s) will be used.` : "No images selected: styled no-photo design."} Google photos are never used.</p></div>
              <div><label className="label" htmlFor="agent">Voice agent</label>
                <Select id="agent" value={agentId} onChange={(e) => setAgentId(e.target.value)}>
                  <option value="">No agent</option>
                  {agents.map((a) => <option key={a.id} value={a.id}>{a.name} ({a.status})</option>)}
                </Select>
                <Button variant="ghost" className="mt-1" loading={busy === "agent"} onClick={budgetAgent}><Bot className="h-4 w-4" />Create “Website Sales – Budget Discovery” agent</Button></div>
            </div>
            <Packages />
            <div className="flex flex-wrap gap-2 border-t border-line pt-4">
              <Button loading={busy === "run"} onClick={() => go(false)}><Play className="h-4 w-4" />Run pipeline (lead + website)</Button>
              <Button variant="outline" disabled={!agentId} loading={busy === "call"} onClick={() => go(true)}><Phone className="h-4 w-4" />Run + Call via compliance gate</Button>
              {agentId && <Link href={`/agents/${agentId}/test?voice=1${leadId ? `&lead=${leadId}` : ""}`} className="inline-flex h-10 items-center gap-2 rounded-full border border-line px-4 text-sm hover:bg-raised">
                <Bot className="h-4 w-4" />Talk to it yourself (browser voice)</Link>}
            </div>
            {agentId && !leadId && <p className="text-xs text-muted">Run the pipeline first so the browser conversation&apos;s outcome is saved on the lead.</p>}
          </section>

          {run && <RunPanel run={run} agentId={agentId} />}
        </>
      )}
    </div>
  );
}

function RunPanel({ run, agentId }: { run: Run; agentId: string }) {
  return (
    <section className="card space-y-4 p-5">
      <div className="flex items-center gap-2"><h2 className="font-medium">4. Status & results</h2>
        <Badge tone={run.status === "completed" ? "success" : run.status === "failed" ? "danger" : "warning"}>{run.status.replace("_", " ")}</Badge></div>
      <ol className="space-y-3">
        {run.steps.map((s) => (
          <li key={s.key} className="flex gap-3 text-sm">
            {s.status === "done" ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600" /> : s.status === "failed" ? <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
              : s.status === "blocked" ? <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" /> : <CircleDashed className="mt-0.5 h-4 w-4 shrink-0 text-muted" />}
            <div className="min-w-0 flex-1 space-y-1">
              <p><b>{STEP_LABEL[s.key]}</b> <Badge tone={TONE[s.status]}>{s.status.replace("_", " ")}</Badge> <span className="text-muted">{s.message}</span></p>
              {s.key === "lead" && run.lead_id && <Link className="text-xs text-accent" href={`/leads/${run.lead_id}`}>Open lead →</Link>}
              {s.preview_path && <a className="inline-flex items-center gap-1 text-xs text-accent" href={`${API_URL}${s.preview_path}`} target="_blank" rel="noopener noreferrer">Open website preview <ExternalLink className="h-3 w-3" /></a>}
              {s.key === "call" && s.simulated && <p className="text-xs text-amber-700">Simulated: no telephony provider is used outside production; nobody was called.</p>}
              {!!s.reasons?.length && (
                <ul className="space-y-1 rounded-xl bg-amber-50 p-3 text-xs text-amber-900">
                  {s.reasons.map((r, i) => <li key={r}><code>{r}</code> — {s.fixes?.[i]}</li>)}
                </ul>
              )}
            </div>
          </li>
        ))}
      </ol>
      {run.outcome ? <OutcomeCard o={run.outcome} /> : (
        <p className="text-sm text-muted">No conversation outcome yet. {agentId ? "Use “Talk to it yourself”, then “End conversation”, to record one." : "Choose an agent to talk to."}</p>
      )}
    </section>
  );
}

function Packages() {
  const [pk, setPk] = useState<Package[]>([]);
  const [open, setOpen] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { pipelineApi.packages().then(setPk).catch(() => {}); }, []);
  const upd = (i: number, k: keyof Package, v: string) => setPk(pk.map((p, j) => j === i ? { ...p, [k]: k === "min" || k === "max" ? Number(v) : v } : p));
  async function save() {
    try { setPk((await pipelineApi.savePackages(pk)).packages); setMsg("Saved. New budget agents will quote only these ranges."); }
    catch (e) { setMsg((e as Error).message); }
  }
  return (
    <div className="rounded-xl border border-line p-3 text-sm">
      <button className="text-accent" onClick={() => setOpen(!open)}>{open ? "Hide" : "Configure"} package price ranges ({pk.length})</button>
      <p className="text-xs text-muted">The budget agent never invents prices: it quotes only these ranges, or asks for the prospect&apos;s budget if none are set.</p>
      {open && (
        <div className="mt-3 space-y-2">
          {pk.map((p, i) => (
            <div key={i} className="grid grid-cols-[1fr_6rem_6rem_5rem_auto] gap-2">
              <Input aria-label="Package name" value={p.name} onChange={(e) => upd(i, "name", e.target.value)} />
              <Input aria-label="Min" type="number" value={p.min} onChange={(e) => upd(i, "min", e.target.value)} />
              <Input aria-label="Max" type="number" value={p.max} onChange={(e) => upd(i, "max", e.target.value)} />
              <Input aria-label="Currency" value={p.currency} maxLength={3} onChange={(e) => upd(i, "currency", e.target.value.toUpperCase())} />
              <Button variant="ghost" onClick={() => setPk(pk.filter((_, j) => j !== i))}>Remove</Button>
            </div>
          ))}
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setPk([...pk, { name: "Starter", min: 0, max: 0, currency: "INR" }])}>Add package</Button>
            <Button onClick={save}>Save</Button>
          </div>
          {msg && <p className="text-xs text-muted">{msg}</p>}
        </div>
      )}
    </div>
  );
}
