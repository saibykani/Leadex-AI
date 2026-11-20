"use client";
import clsx from "clsx";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ArrowLeft, ArrowRight, Bot, Building2, Check, FileUp, Globe2, Plug, Rocket, Search, UserPlus } from "lucide-react";
import { api, API_URL, session } from "@/lib/api";
import { growth, type Onboarding } from "@/lib/growth";
import { useSession } from "@/lib/session-context";
import { Alert, Badge, Button, Input, PageHeader, Progress, Select, Skeleton, useToast, LinkButton } from "@/components/ui";

const ICONS: Record<string, typeof Rocket> = { profile: Building2, integrations: Plug, businesses: Search, agent: Bot, website: Globe2, teammate: UserPlus };

export default function OnboardingPage() {
  const { current } = useSession();
  const [state, setState] = useState<Onboarding | null>(null);
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => growth.onboarding().then((s) => { setState(s); return s; }), []);
  useEffect(() => {
    load().then((s) => { const i = s.steps.findIndex((x) => !x.done && !x.skipped); setStep(i < 0 ? 0 : i); }).catch((e) => setError(e.message));
  }, [load, current.organization.id]);

  const mark = async (key: string, action: "complete" | "skip", profile?: Record<string, string>) => {
    try {
      const s = await growth.onboardingStep(key, action, profile);
      setState(s);
      setStep((i) => Math.min(i + 1, s.steps.length - 1));
    } catch (e) { setError((e as Error).message); }
  };
  const refresh = async () => { await load(); setStep((i) => Math.min(i + 1, 5)); };

  if (!state) return <div className="space-y-4"><Skeleton className="h-24 w-full" /><Skeleton className="h-96 w-full" /></div>;
  const s = state.steps[step];
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader eyebrow="Get started" title={<>Launch <span className="text-gradient">{current.organization.name}</span></>}
        description="Six steps from empty workspace to a live AI growth engine. Progress is saved for your whole team." />
      {error && <Alert>{error}</Alert>}
      <div className="card p-5">
        <div className="mb-3 flex items-center justify-between text-sm"><span className="font-medium">{state.completed} of {state.total} complete</span><span className="text-muted">{state.percent}%</span></div>
        <Progress value={state.percent} />
      </div>

      <div className="grid gap-6 md:grid-cols-[240px_1fr]">
        <ol className="flex gap-2 overflow-x-auto md:flex-col md:overflow-visible">
          {state.steps.map((x, i) => {
            const Icon = ICONS[x.key] ?? Rocket;
            const on = i === step;
            return (
              <li key={x.key} className="shrink-0">
                <button onClick={() => setStep(i)} className={clsx("relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition", on ? "text-ink" : "text-muted hover:bg-raised")}>
                  {on && <motion.span layoutId="onb-step" className="absolute inset-0 rounded-xl bg-surface shadow-card ring-1 ring-line" />}
                  <span className={clsx("relative grid h-8 w-8 shrink-0 place-items-center rounded-full transition", x.done ? "bg-success text-white" : on ? "bg-brand text-white shadow-glow" : "bg-raised ring-1 ring-line")}>
                    {x.done ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                  </span>
                  <span className="relative hidden md:block"><span className="block font-medium">{x.title}</span>{x.skipped && <span className="text-xs text-muted">Skipped</span>}{x.done && x.evidence && <span className="text-xs text-muted">{x.evidence}</span>}</span>
                </button>
              </li>
            );
          })}
        </ol>

        <div className="card relative min-h-[380px] overflow-hidden p-6 sm:p-8">
          <div aria-hidden className="lx-blob absolute -right-20 -top-20 h-56 w-56 rounded-full bg-[#5e5ce6]/10 blur-3xl" />
          <AnimatePresence mode="wait">
            <motion.div key={s.key} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} transition={{ duration: 0.25 }} className="relative">
              <div className="mb-1 flex items-center gap-2"><span className="eyebrow">Step {step + 1} of {state.total}</span>{s.done && <Badge tone="success" dot>Done{s.source === "data" ? " · detected from your data" : ""}</Badge>}</div>
              {s.key === "profile" && <ProfileStep initial={state.profile} onSave={(p) => mark("profile", "complete", p)} />}
              {s.key === "integrations" && <IntegrationsStep onDone={() => mark("integrations", "complete")} />}
              {s.key === "businesses" && <BusinessesStep done={s.done} onRefresh={refresh} />}
              {s.key === "agent" && <AgentStep done={s.done} onRefresh={refresh} />}
              {s.key === "website" && <WebsiteStep done={s.done} onRefresh={refresh} profile={state.profile} />}
              {s.key === "teammate" && <TeammateStep done={s.done} onRefresh={load} />}
              <div className="mt-8 flex items-center justify-between border-t border-line pt-5">
                <Button variant="ghost" size="sm" onClick={() => setStep((i) => Math.max(0, i - 1))} disabled={step === 0}><ArrowLeft className="h-4 w-4" />Back</Button>
                <div className="flex gap-2">
                  {!s.done && <Button variant="ghost" size="sm" onClick={() => mark(s.key, "skip")}>Skip for now</Button>}
                  {step < state.total - 1 ? <Button variant="outline" size="sm" onClick={() => setStep((i) => i + 1)}>Next<ArrowRight className="h-4 w-4" /></Button>
                    : <LinkButton href="/dashboard" variant="gradient" size="sm"><Rocket className="h-4 w-4" />Go to Command Center</LinkButton>}
                </div>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}

function StepHead({ title, body }: { title: string; body: ReactNode }) {
  return <div className="mb-5"><h2 className="text-xl font-semibold tracking-tight">{title}</h2><p className="mt-1 text-sm text-muted">{body}</p></div>;
}

function ProfileStep({ initial, onSave }: { initial: Record<string, string>; onSave: (p: Record<string, string>) => Promise<void> }) {
  const [p, setP] = useState<Record<string, string>>({ industry: "", city: "", team_size: "", goal: "", website: "", ...initial });
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: { target: { value: string } }) => setP((x) => ({ ...x, [k]: e.target.value }));
  return (
    <form onSubmit={async (e) => { e.preventDefault(); setBusy(true); await onSave(Object.fromEntries(Object.entries(p).filter(([, v]) => v))); setBusy(false); }}>
      <StepHead title="Tell us about your company" body="Used to tailor templates, discovery defaults and your daily briefing." />
      <div className="grid gap-4 sm:grid-cols-2">
        <label><span className="label">Industry you sell to</span><Input value={p.industry} onChange={set("industry")} placeholder="e.g. Dental clinics" /></label>
        <label><span className="label">Primary city</span><Input value={p.city} onChange={set("city")} placeholder="e.g. Pune" /></label>
        <label><span className="label">Team size</span><Select value={p.team_size} onChange={set("team_size")} className="h-12 w-full"><option value="">Select…</option>{["Just me", "2–5", "6–20", "21–100", "100+"].map((x) => <option key={x}>{x}</option>)}</Select></label>
        <label><span className="label">Website</span><Input value={p.website} onChange={set("website")} placeholder="https://" /></label>
        <label className="sm:col-span-2"><span className="label">Main growth goal</span><Input value={p.goal} onChange={set("goal")} placeholder="e.g. Book 20 qualified demos a month" /></label>
      </div>
      <Button type="submit" className="mt-5" loading={busy}>Save profile<ArrowRight className="h-4 w-4" /></Button>
    </form>
  );
}

type Integration = { provider: string; label: string; status: string };
function IntegrationsStep({ onDone }: { onDone: () => void }) {
  const { can } = useSession();
  const [rows, setRows] = useState<Integration[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api<Integration[]>("/integrations", {}, true).then(setRows).catch((e) => setErr(e.message)); }, []);
  return (
    <div>
      <StepHead title="Connect your channels" body="Live status of each provider. Anything not configured runs in clearly-labelled simulation mode." />
      {err ? <p className="text-sm text-muted">{can("integrations:manage") ? err : "Your role can't view integrations — an admin can connect them."}</p> : !rows ? <Skeleton className="h-40 w-full" /> : (
        <ul className="grid gap-2 sm:grid-cols-2">
          {rows.map((r, i) => (
            <motion.li key={r.provider} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }} className="flex items-center justify-between rounded-xl border border-line px-3 py-2.5 text-sm">
              <span className="font-medium">{r.label}</span>
              <Badge tone={r.status === "connected" || r.status === "active" ? "success" : r.status === "error" ? "danger" : "neutral"} dot>{r.status.replace(/_/g, " ")}</Badge>
            </motion.li>
          ))}
        </ul>
      )}
      <div className="mt-5 flex flex-wrap gap-2">
        <Button onClick={onDone}><Check className="h-4 w-4" />Mark as reviewed</Button>
        {can("integrations:manage") && <LinkButton href="/integrations" variant="outline">Open integrations</LinkButton>}
      </div>
    </div>
  );
}

function BusinessesStep({ done, onRefresh }: { done: boolean; onRefresh: () => Promise<void> }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const upload = async (file: File) => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch(`${API_URL}/api/v1/discovery/import`, { method: "POST", body: fd, headers: { Authorization: `Bearer ${session.access ?? ""}`, "X-Organization-Id": session.org ?? "" } });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body?.error?.message ?? "Import failed");
      toast(`Imported ${body.results_count ?? 0} rows (${body.new_count ?? 0} new)`, "success");
      await onRefresh();
    } catch (e) { toast((e as Error).message, "danger"); } finally { setBusy(false); }
  };
  return (
    <div>
      <StepHead title="Bring in your first businesses" body="Import a CSV of prospects you already have consent for, or run a discovery search." />
      <div className="grid gap-3 sm:grid-cols-2">
        <label className={clsx("group flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-line p-6 text-center transition hover:border-accent/50 hover:bg-accent/5", busy && "pointer-events-none opacity-60")}>
          <FileUp className="h-7 w-7 text-accent transition group-hover:-translate-y-0.5" />
          <span className="mt-2 text-sm font-medium">{busy ? "Importing…" : "Upload CSV"}</span>
          <span className="text-xs text-muted">name, city, phone, email, website…</span>
          <input type="file" accept=".csv,text/csv" className="sr-only" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        </label>
        <Link href="/discovery" className="group flex flex-col items-center justify-center rounded-2xl border border-line bg-brand-soft p-6 text-center transition hover:-translate-y-0.5 hover:shadow-card">
          <Search className="h-7 w-7 text-accent transition group-hover:scale-110" />
          <span className="mt-2 text-sm font-medium">Run discovery</span>
          <span className="text-xs text-muted">Search by industry & city</span>
        </Link>
      </div>
      {done && <p className="mt-4 text-sm text-success">You already have businesses or leads in this workspace.</p>}
    </div>
  );
}

type Tpl = { key: string; name: string; industry: string; purpose: string };
function AgentStep({ done, onRefresh }: { done: boolean; onRefresh: () => Promise<void> }) {
  const toast = useToast();
  const [tpls, setTpls] = useState<Tpl[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => { api<{ items: Tpl[] }>("/agents/templates", {}, true).then((r) => setTpls(r.items)).catch(() => setTpls([])); }, []);
  const create = async (t: Tpl) => {
    setBusy(t.key);
    try { await api("/agents/from-template", { method: "POST", body: JSON.stringify({ template_key: t.key }) }, true); toast(`Created “${t.name}”`, "success"); await onRefresh(); }
    catch (e) { toast((e as Error).message, "danger"); } finally { setBusy(null); }
  };
  return (
    <div>
      <StepHead title="Create your first AI voice agent" body="Pick a template — you can edit the script, voice and guardrails afterwards." />
      {!tpls ? <Skeleton className="h-48 w-full" /> : tpls.length === 0 ? <p className="text-sm text-muted">Agent templates aren&apos;t available for your role.</p> : (
        <ul className="grid max-h-80 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
          {tpls.map((t) => (
            <li key={t.key}>
              <button onClick={() => create(t)} disabled={!!busy} className="card-hover flex h-full w-full flex-col rounded-xl border border-line bg-surface p-3 text-left disabled:opacity-60">
                <span className="flex items-center gap-2 text-sm font-medium"><Bot className="h-4 w-4 text-accent" />{t.name}</span>
                <span className="mt-1 line-clamp-2 text-xs text-muted">{t.purpose}</span>
                <span className="mt-2 text-[11px] font-medium text-accent">{busy === t.key ? "Creating…" : "Use template →"}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {done && <p className="mt-4 text-sm text-success">You already have an agent. <Link href="/agents" className="underline">Open agents</Link></p>}
    </div>
  );
}

function WebsiteStep({ done, onRefresh, profile }: { done: boolean; onRefresh: () => Promise<void>; profile: Record<string, string> }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [tpl, setTpl] = useState("professional_services");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const gen = async () => {
    setBusy(true);
    try {
      const r = await api<{ id: string; preview_path: string }>("/websites/generate", { method: "POST", body: JSON.stringify({ template_key: tpl, business: { name, city: profile.city || undefined, industry: profile.industry || undefined } }) }, true);
      setPreview(`${API_URL}${r.preview_path}`);
      toast("Website demo generated", "success");
      await onRefresh();
    } catch (e) { toast((e as Error).message, "danger"); } finally { setBusy(false); }
  };
  return (
    <div>
      <StepHead title="Generate a website demo" body="Show a prospect what their new site could look like — generated in seconds from a template." />
      <div className="grid gap-3 sm:grid-cols-[1fr_200px_auto]">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Prospect business name" aria-label="Business name" />
        <Select value={tpl} onChange={(e) => setTpl(e.target.value)} className="h-12" aria-label="Template">
          {["professional_services", "real_estate", "clinic", "restaurant", "interior_design", "construction", "retail", "education", "architecture", "corporate"].map((k) => <option key={k} value={k}>{k.replace(/_/g, " ")}</option>)}
        </Select>
        <Button onClick={gen} disabled={!name.trim()} loading={busy} className="h-12"><Globe2 className="h-4 w-4" />Generate</Button>
      </div>
      {preview && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mt-4 overflow-hidden rounded-2xl border border-line shadow-lift">
          <div className="flex items-center gap-1.5 border-b border-line bg-raised px-3 py-2"><span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" /><span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" /><span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" /><span className="ml-2 truncate text-xs text-muted">Preview</span></div>
          <iframe src={preview} title="Website preview" className="h-72 w-full bg-white" sandbox="" />
        </motion.div>
      )}
      {done && !preview && <p className="mt-4 text-sm text-success">You already generated a website. <Link href="/websites" className="underline">Open Website Studio</Link></p>}
    </div>
  );
}

function TeammateStep({ done, onRefresh }: { done: boolean; onRefresh: () => Promise<unknown> }) {
  const { current, can } = useSession();
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("Sales Rep");
  const [busy, setBusy] = useState(false);
  const invite = async () => {
    setBusy(true);
    try { await api(`/organizations/${current.organization.id}/members`, { method: "POST", body: JSON.stringify({ email, role }) }); toast(`Added ${email}`, "success"); setEmail(""); await onRefresh(); }
    catch (e) { toast((e as Error).message, "danger"); } finally { setBusy(false); }
  };
  return (
    <div>
      <StepHead title="Invite a teammate" body="Add an existing LeadexAI user to this workspace with a role." />
      {!can("members:write") ? <p className="text-sm text-muted">Your role can&apos;t add members.</p> : (
        <div className="grid gap-3 sm:grid-cols-[1fr_160px_auto]">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="teammate@company.com" aria-label="Email" />
          <Select value={role} onChange={(e) => setRole(e.target.value)} className="h-12" aria-label="Role">{["Admin", "Manager", "Sales Rep", "Viewer"].map((r) => <option key={r}>{r}</option>)}</Select>
          <Button onClick={invite} disabled={!email.includes("@")} loading={busy} className="h-12"><UserPlus className="h-4 w-4" />Add</Button>
        </div>
      )}
      {done && <p className="mt-4 text-sm text-success">Your workspace has more than one member.</p>}
    </div>
  );
}
