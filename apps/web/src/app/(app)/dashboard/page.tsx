"use client";
import clsx from "clsx";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";
import {
  Activity, AlarmClock, ArrowRight, ArrowUpRight, Bot, CheckCircle2, Circle, Flame, Globe2, History, LineChart, Megaphone,
  Rocket, Sparkles, Target, Trophy, Users, Wallet,
} from "lucide-react";
import { api, type AuditLog, type Page } from "@/lib/api";
import { statusLabel, timeAgo } from "@/lib/crm";
import { growth, fmtMoney, type Analytics, type Briefing, type Forecast, type Onboarding, type Opportunity, type Overview, type PipelineValue } from "@/lib/growth";
import { useSession } from "@/lib/session-context";
import { Alert, AnimatedNumber, Badge, Button, Card, EmptyState, Progress, Skeleton, StatCard, LinkButton } from "@/components/ui";

const GREETING = () => { const h = new Date().getHours(); return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"; };

export default function CommandCenter() {
  const { current, can, me } = useSession();
  const canLeads = can("leads:read");
  const [brief, setBrief] = useState<Briefing | null>(null);
  const [ov, setOv] = useState<Overview | null>(null);
  const [pv, setPv] = useState<PipelineValue | null>(null);
  const [fc, setFc] = useState<Forecast | null>(null);
  const [an, setAn] = useState<Analytics | null>(null);
  const [opps, setOpps] = useState<Opportunity[] | null>(null);
  const [onb, setOnb] = useState<Onboarding | null>(null);
  const [logs, setLogs] = useState<Page<AuditLog> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fail = (e: Error) => setError(e.message);
    if (canLeads) {
      growth.briefing().then(setBrief).catch(fail);
      growth.overview(30).then(setOv).catch(fail);
      growth.pipelineValue().then(setPv).catch(fail);
      growth.forecast().then(setFc).catch(fail);
      growth.analytics(8).then(setAn).catch(fail);
      growth.opportunities(6).then(setOpps).catch(fail);
    }
    growth.onboarding().then(setOnb).catch(() => {});
    if (can("audit:read")) api<Page<AuditLog>>("/audit-logs?page_size=8", {}, true).then(setLogs).catch(() => {});
  }, [current.organization.id, can, canLeads]);

  const firstName = me.user.full_name.split(" ")[0];
  const series = (k: keyof Overview["totals"]) => ov?.points.map((p) => p[k]) ?? [];
  const leadDelta = ov ? ov.totals.leads - ov.previous.leads : null;
  const openValue = pv ? Object.entries(pv.open_value) : [];

  return (
    <div className="space-y-6">
      {/* ---------------------------------------------------------------- hero */}
      <Hero name={firstName} org={current.organization.name} brief={brief} canLeads={canLeads} />
      {error && <Alert>{error}</Alert>}

      {!canLeads ? (
        <EmptyState icon={<Sparkles className="h-5 w-5" />} title="Limited access" body="Your role doesn't include lead access, so growth analytics are hidden. Ask an admin if you need more visibility." />
      ) : (
        <>
          {/* ---------------------------------------------------------------- KPIs */}
          <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            <StatCard label="New leads · 30d" value={ov?.totals.leads} icon={<Users className="h-4 w-4" />} spark={series("leads")}
              delta={leadDelta !== null && ov && ov.previous.leads > 0 ? { value: leadDelta } : null} hint={ov ? `${ov.previous.leads} in previous 30d` : undefined} />
            <StatCard label="Conversions · 30d" value={ov?.totals.conversions} icon={<Trophy className="h-4 w-4" />} tone="success" spark={series("conversions")} sparkColor="#1a7f37"
              hint={brief ? `${brief.facts.converted} converted all-time` : undefined} />
            <StatCard label="Open pipeline" tone="violet" icon={<Wallet className="h-4 w-4" />} spark={series("outcomes_with_budget")} sparkColor="#5e5ce6"
              value={pv === null ? undefined : openValue.length ? <span className="text-[24px] sm:text-[28px]">{fmtMoney(openValue[0][1], openValue[0][0])}</span> : <span className="text-muted">—</span>}
              hint={pv ? (openValue.length > 1 ? `+ ${openValue.slice(1).map(([c, v]) => fmtMoney(v, c)).join(", ")}` : `${pv.leads_without_budget} open leads without stated budget`) : undefined} />
            <StatCard label="AI agent runs · 30d" value={ov?.totals.agent_runs} icon={<Bot className="h-4 w-4" />} tone="neutral" spark={series("agent_runs")} sparkColor="#bf5af2"
              hint={ov ? `${ov.totals.calls} calls · ${ov.totals.websites} websites generated` : undefined} />
          </div>

          {/* ---------------------------------------------------------------- funnel + pipeline */}
          <div className="grid gap-4 lg:grid-cols-5">
            <Card className="lg:col-span-3" title="Conversion funnel" icon={<Target className="h-4 w-4 text-accent" />}
              subtitle="Leads that have reached each stage (from status history)"
              action={<Link href="/insights" className="flex items-center gap-1 text-xs font-medium text-accent hover:underline">Deep dive<ArrowRight className="h-3 w-3" /></Link>}>
              {!an ? <Skeleton className="h-64 w-full" /> : an.funnel[0]?.count === 0
                ? <EmptyState compact title="No leads yet" body="Run a discovery search or import a CSV — your funnel animates in as leads progress." action={<LinkButton href="/discovery" size="sm">Run discovery</LinkButton>} />
                : <Funnel rows={an.funnel} />}
            </Card>
            <Card className="lg:col-span-2" title="Pipeline value by stage" icon={<Wallet className="h-4 w-4 text-violet-500" />}
              subtitle="Midpoint of stated budgets · nothing estimated">
              {!pv ? <Skeleton className="h-64 w-full" /> : <PipelineStages pv={pv} />}
            </Card>
          </div>

          {/* ---------------------------------------------------------------- opportunities + forecast */}
          <div className="grid gap-4 lg:grid-cols-5">
            <Card className="lg:col-span-3" title="Top opportunities" icon={<Flame className="h-4 w-4 text-orange-500" />}
              subtitle="Open leads with a stated budget, ranked by interest then size"
              action={<Link href="/leads" className="flex items-center gap-1 text-xs font-medium text-accent hover:underline">All leads<ArrowRight className="h-3 w-3" /></Link>}>
              {!opps ? <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14 w-full" />)}</div>
                : opps.length === 0 ? <EmptyState compact title="No budgeted opportunities yet" body="When an AI agent conversation captures a budget, the best opportunities surface here automatically." />
                : <Opportunities rows={opps} />}
            </Card>
            <Card className="lg:col-span-2" title="Revenue forecast" icon={<LineChart className="h-4 w-4 text-accent" />} subtitle="Transparent, history-based">
              {!fc ? <Skeleton className="h-48 w-full" /> : <ForecastCard fc={fc} />}
            </Card>
          </div>

          {/* ---------------------------------------------------------------- agents + onboarding + activity */}
          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="AI agent performance" icon={<Bot className="h-4 w-4 text-accent" />} subtitle="Runs, outcomes and latency">
              {!an ? <Skeleton className="h-40 w-full" /> : <AgentPerf an={an} />}
            </Card>
            <Card title="Launch checklist" icon={<Rocket className="h-4 w-4 text-accent" />} subtitle={onb ? `${onb.completed} of ${onb.total} complete` : "Your first-run setup"}
              action={<Link href="/onboarding" className="text-xs font-medium text-accent hover:underline">Open</Link>}>
              {!onb ? <Skeleton className="h-40 w-full" /> : <Checklist onb={onb} />}
            </Card>
            <Card title="Activity" icon={<History className="h-4 w-4 text-accent" />} subtitle="Latest events in this workspace">
              {!can("audit:read") ? <p className="text-sm text-muted">Your role can&apos;t view the audit log.</p>
                : !logs ? <Skeleton className="h-40 w-full" /> : logs.items.length === 0 ? <p className="py-6 text-center text-sm text-muted">No activity recorded yet.</p> : (
                <ol className="relative space-y-3 before:absolute before:bottom-1 before:left-[5px] before:top-1 before:w-px before:bg-line">
                  {logs.items.map((l, i) => (
                    <motion.li key={l.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }} className="relative flex items-start gap-3 pl-0 text-sm">
                      <span className="relative mt-1.5 h-[11px] w-[11px] shrink-0 rounded-full border-2 border-surface bg-accent" />
                      <span className="min-w-0 flex-1"><span className="block truncate font-medium">{statusLabel(l.action.replace(/\./g, " "))}</span>
                        <span className="text-xs text-muted">{l.entity_type ?? "workspace"} · {timeAgo(l.created_at)}</span></span>
                    </motion.li>
                  ))}
                </ol>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

/* ================================================================== hero + briefing */
function Hero({ name, org, brief, canLeads }: { name: string; org: string; brief: Briefing | null; canLeads: boolean }) {
  const reduce = useReducedMotion();
  const f = brief?.facts;
  return (
    <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="ring-gradient relative overflow-hidden rounded-3xl border border-line bg-surface p-6 shadow-card sm:p-8">
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="lx-blob absolute -right-24 -top-24 h-72 w-72 rounded-full bg-[#5e5ce6]/20 blur-3xl" />
        <div className="lx-blob lx-delay-2 absolute -bottom-32 left-1/3 h-72 w-72 rounded-full bg-[#0a84ff]/15 blur-3xl" />
        <div className="lx-blob lx-delay-4 absolute -left-16 top-0 h-56 w-56 rounded-full bg-[#bf5af2]/12 blur-3xl" />
        <div className="bg-grid absolute inset-0 opacity-40 [mask-image:radial-gradient(ellipse_at_top_right,black,transparent_70%)]" />
      </div>
      <div className="relative grid gap-6 lg:grid-cols-[1.4fr_1fr] lg:items-end">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="eyebrow">{org} · Growth Command Center</span>
          </div>
          <h1 className="mt-2 font-display text-[30px] font-bold leading-tight tracking-tight sm:text-[40px]">
            {GREETING()}, <span className="text-gradient">{name}</span>
          </h1>
          <div className="mt-4 max-w-2xl rounded-2xl border border-line bg-surface/70 p-4 backdrop-blur">
            <div className="mb-2 flex items-center gap-2 text-[13px] font-semibold">
              <span className="relative grid h-6 w-6 place-items-center rounded-full bg-brand text-white">
                <Sparkles className="h-3.5 w-3.5" />
                {!reduce && <span className="absolute inset-0 animate-pulse-ring rounded-full bg-accent/40" />}
              </span>
              Daily AI briefing
              {brief && <Badge tone={brief.mode === "ollama" ? "violet" : "neutral"} className="ml-auto">{brief.mode === "ollama" ? `Polished by ${brief.model}` : "Computed from live data"}</Badge>}
            </div>
            {!canLeads ? <p className="text-sm text-muted">Briefings need lead access.</p> : !brief ? (
              <div className="space-y-2"><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-4/5" /></div>
            ) : (
              <ul className="space-y-1.5 text-[14px] leading-relaxed text-neutral-700">
                {(brief.mode === "ollama" ? [brief.text] : brief.lines).map((l, i) => (
                  <motion.li key={i} initial={reduce ? false : { opacity: 0, y: 4, filter: "blur(3px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                    transition={{ delay: 0.25 + i * 0.18, duration: 0.4 }} className="flex gap-2">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />{l}
                  </motion.li>
                ))}
              </ul>
            )}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: "Hot leads", value: f?.hot_leads, icon: Flame, href: "/copilot?q=Show%20hot%20leads%20with%20high%20interest", tone: "text-orange-500" },
            { label: "Overdue tasks", value: f?.overdue_tasks, icon: AlarmClock, href: "/leads", tone: f?.overdue_tasks ? "text-danger" : "text-muted" },
            { label: "Campaigns live", value: f?.campaigns_running, icon: Megaphone, href: "/campaigns", tone: "text-accent" },
            { label: "Sites published", value: f?.websites_published, icon: Globe2, href: "/websites", tone: "text-success" },
          ].map((m, i) => (
            <motion.div key={m.label} initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.15 + i * 0.06 }}>
              <Link href={m.href} className="card card-hover group block p-4 focus-ring">
                <div className="flex items-center justify-between text-xs text-muted">{m.label}<m.icon className={clsx("h-4 w-4", m.tone)} /></div>
                <div className="mt-1 flex items-end justify-between">
                  <span className="font-display text-2xl font-semibold">{m.value === undefined ? <Skeleton className="h-7 w-10" /> : <AnimatedNumber value={m.value} />}</span>
                  <ArrowUpRight className="h-4 w-4 text-muted opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100" />
                </div>
              </Link>
            </motion.div>
          ))}
          <Link href="/copilot" className="col-span-2 flex items-center justify-between rounded-2xl bg-brand px-4 py-3 text-sm font-medium text-white shadow-glow transition hover:-translate-y-0.5 hover:brightness-110">
            <span className="flex items-center gap-2"><Sparkles className="h-4 w-4" />Ask your pipeline anything</span><ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </motion.section>
  );
}

/* ================================================================== funnel */
function Funnel({ rows }: { rows: Analytics["funnel"] }) {
  const max = Math.max(1, rows[0]?.count ?? 1);
  return (
    <div className="space-y-1.5">
      {rows.map((r, i) => {
        const pct = (r.count / max) * 100;
        const prev = i > 0 ? rows[i - 1].count : null;
        const step = prev ? Math.round((r.count / prev) * 100) : null;
        return (
          <div key={r.stage} className="group grid grid-cols-[110px_1fr_auto] items-center gap-3 text-sm sm:grid-cols-[150px_1fr_auto]">
            <span className="truncate text-[13px] text-muted">{statusLabel(r.stage)}</span>
            <div className="relative h-7 overflow-hidden rounded-lg bg-raised">
              <motion.div className={clsx("absolute inset-y-0 left-0 rounded-lg", r.stage === "converted" ? "bg-gradient-to-r from-emerald-500 to-emerald-400" : "bg-brand")}
                style={{ opacity: 0.35 + 0.65 * (1 - i / rows.length) }}
                initial={{ width: 0 }} animate={{ width: `${Math.max(pct, r.count ? 2 : 0)}%` }} viewport={{ once: true }} transition={{ duration: 0.9, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }} />
              <span className="relative flex h-full items-center px-2.5 text-xs font-semibold tabular-nums text-ink">{r.count}</span>
            </div>
            <span className="w-12 text-right text-[11px] tabular-nums text-muted">{step !== null ? `${step}%` : ""}</span>
          </div>
        );
      })}
      <p className="pt-2 text-[11px] text-muted">Right column: share of the previous stage that reached this stage.</p>
    </div>
  );
}

/* ================================================================== pipeline value */
function PipelineStages({ pv }: { pv: PipelineValue }) {
  const cur = Object.keys(pv.open_value)[0];
  const rows = pv.stages.filter((s) => s.leads > 0);
  if (!rows.length) return <EmptyState compact title="No pipeline yet" body="Stage values appear when leads have conversation outcomes with a stated budget." />;
  const max = Math.max(1, ...rows.map((s) => (cur ? s.value[cur] ?? 0 : 0)));
  return (
    <div>
      <ul className="space-y-2.5">
        {rows.slice(0, 8).map((s, i) => {
          const v = cur ? s.value[cur] ?? 0 : 0;
          return (
            <li key={s.stage}>
              <div className="mb-1 flex items-center justify-between text-[13px]">
                <span className="text-neutral-700">{statusLabel(s.stage)} <span className="text-xs text-muted">· {s.leads} lead{s.leads !== 1 && "s"}</span></span>
                <span className="font-medium tabular-nums">{v ? fmtMoney(v, cur!) : <span className="text-xs font-normal text-muted">no budget</span>}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-raised">
                <motion.div className="h-full rounded-full bg-gradient-to-r from-[#5e5ce6] to-[#bf5af2]" initial={{ width: 0 }} animate={{ width: `${(v / max) * 100}%` }} viewport={{ once: true }} transition={{ duration: 0.8, delay: i * 0.05 }} />
              </div>
            </li>
          );
        })}
      </ul>
      {pv.leads_without_budget > 0 && <p className="mt-4 rounded-xl bg-raised px-3 py-2 text-xs text-muted">{pv.leads_without_budget} open leads have no stated budget yet and are counted but not valued.</p>}
    </div>
  );
}

/* ================================================================== opportunities */
const INTEREST: Record<string, "success" | "accent" | "warning" | "neutral" | "danger"> = { high: "success", medium: "accent", low: "warning", unknown: "neutral", none: "danger" };
function Opportunities({ rows }: { rows: Opportunity[] }) {
  return (
    <ul className="-mx-2 divide-y divide-line">
      {rows.map((o, i) => (
        <motion.li key={o.lead_id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
          <Link href={`/leads/${o.lead_id}`} className="group flex items-center gap-3 rounded-xl px-2 py-3 transition hover:bg-raised/60">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-soft text-sm font-bold text-accent">{o.business_name[0]}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{o.business_name}</span>
              <span className="block truncate text-xs text-muted">{statusLabel(o.status)}{o.city && ` · ${o.city}`}{o.timeline && ` · ${o.timeline}`}</span>
            </span>
            <Badge tone={INTEREST[o.interest] ?? "neutral"} dot className="hidden capitalize sm:inline-flex">{o.interest}</Badge>
            <span className="w-24 text-right text-sm font-semibold tabular-nums">{fmtMoney(o.budget_mid, o.currency)}</span>
            <ArrowRight className="h-4 w-4 text-muted transition group-hover:translate-x-0.5 group-hover:text-accent" />
          </Link>
        </motion.li>
      ))}
    </ul>
  );
}

/* ================================================================== forecast */
function ForecastCard({ fc }: { fc: Forecast }) {
  if (fc.status === "insufficient_data") {
    return (
      <div>
        <div className="flex items-center gap-3 rounded-2xl bg-raised p-4">
          <div className="relative h-14 w-14 shrink-0">
            <svg viewBox="0 0 36 36" className="h-14 w-14 -rotate-90"><circle cx="18" cy="18" r="15.5" fill="none" stroke="rgb(var(--c-line))" strokeWidth="3" />
              <motion.circle cx="18" cy="18" r="15.5" fill="none" stroke="url(#fcg)" strokeWidth="3" strokeLinecap="round" strokeDasharray="97.4"
                initial={{ strokeDashoffset: 97.4 }} animate={{ strokeDashoffset: 97.4 * (1 - Math.min(1, fc.closed_deals / fc.min_closed_required)) }} transition={{ duration: 1 }} />
              <defs><linearGradient id="fcg"><stop stopColor="#0a84ff" /><stop offset="1" stopColor="#bf5af2" /></linearGradient></defs></svg>
            <span className="absolute inset-0 grid place-items-center text-xs font-semibold">{fc.closed_deals}/{fc.min_closed_required}</span>
          </div>
          <div className="text-sm"><div className="font-medium">Insufficient data</div><div className="text-muted">{fc.message}</div></div>
        </div>
        <p className="mt-3 text-[11px] leading-relaxed text-muted">We never guess. Once enough deals close, the forecast uses: <span className="font-mono">{fc.formula}</span></p>
      </div>
    );
  }
  return (
    <div>
      <div className="space-y-1">
        {Object.entries(fc.forecast).map(([c, v]) => (
          <div key={c} className="font-display text-3xl font-semibold tracking-tight"><AnimatedNumber value={v} format={(n) => fmtMoney(n, c)} /></div>
        ))}
        {Object.keys(fc.forecast).length === 0 && <div className="text-sm text-muted">No open leads with a stated budget.</div>}
      </div>
      <div className="mt-1 text-xs text-muted">Expected value of open pipeline · win rate {((fc.win_rate ?? 0) * 100).toFixed(0)}% ({fc.won}/{fc.closed_deals} closed)</div>
      <ul className="mt-4 space-y-1.5">
        {fc.stages.slice(0, 5).map((s) => (
          <li key={s.stage} className="flex items-center justify-between text-xs">
            <span className="text-neutral-700">{statusLabel(s.stage)}</span>
            <span className="tabular-nums text-muted">{(s.rate * 100).toFixed(0)}% <span className="text-[10px]">({s.rate_source})</span></span>
          </li>
        ))}
      </ul>
      <details className="mt-3 text-[11px] text-muted"><summary className="cursor-pointer select-none font-medium text-accent">How is this calculated?</summary><p className="mt-1 font-mono leading-relaxed">{fc.formula}</p></details>
    </div>
  );
}

/* ================================================================== agents */
function AgentPerf({ an }: { an: Analytics }) {
  if (!an.agents.length) return <EmptyState compact title="No agent runs yet" body="Create an agent from a template and test it — performance shows up here." action={<LinkButton href="/agents" size="sm" variant="soft">Open agents</LinkButton>} />;
  return (
    <ul className="space-y-3">
      {an.agents.slice(0, 4).map((a) => {
        const out = Object.entries(a.outcomes);
        const total = out.reduce((s, [, n]) => s + n, 0);
        return (
          <li key={a.agent_id} className="rounded-xl border border-line p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="flex min-w-0 items-center gap-2 text-sm font-medium"><span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand text-white"><Bot className="h-3.5 w-3.5" /></span><span className="truncate">{a.name}</span></span>
              <span className="shrink-0 text-xs text-muted">{a.runs} runs{a.avg_latency_ms !== null && ` · ${a.avg_latency_ms}ms`}</span>
            </div>
            {total > 0 && (
              <div className="mt-2 flex h-1.5 overflow-hidden rounded-full bg-raised">
                {out.map(([k, n]) => <motion.div key={k} title={`${k}: ${n}`} initial={{ width: 0 }} animate={{ width: `${(n / total) * 100}%` }} transition={{ duration: 0.8 }}
                  className={clsx(k === "high" ? "bg-success" : k === "medium" ? "bg-accent" : k === "low" ? "bg-amber-500" : k === "none" ? "bg-danger" : "bg-neutral-400")} />)}
              </div>
            )}
            {total > 0 && <div className="mt-1 text-[11px] text-muted">{out.map(([k, n]) => `${n} ${k}`).join(" · ")} interest</div>}
          </li>
        );
      })}
    </ul>
  );
}

/* ================================================================== checklist */
function Checklist({ onb }: { onb: Onboarding }) {
  return (
    <div>
      <Progress value={onb.percent} />
      <ul className="mt-4 space-y-2">
        {onb.steps.map((s) => (
          <li key={s.key} className="flex items-center gap-2.5 text-sm">
            {s.done ? <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring" }}><CheckCircle2 className="h-[18px] w-[18px] text-success" /></motion.span> : <Circle className="h-[18px] w-[18px] text-line" />}
            <span className={clsx("flex-1", s.done ? "text-muted line-through decoration-line" : "text-neutral-700")}>{s.title}</span>
            {s.skipped && <span className="text-[11px] text-muted">skipped</span>}
          </li>
        ))}
      </ul>
      {onb.completed < onb.total && <Link href="/onboarding" className="mt-4 flex items-center justify-center gap-1 rounded-xl bg-accent/10 py-2 text-sm font-medium text-accent transition hover:bg-accent/15">Continue setup<ArrowRight className="h-4 w-4" /></Link>}
      {onb.completed === onb.total && <p className="mt-4 flex items-center gap-2 text-sm text-success"><Activity className="h-4 w-4" />Workspace fully set up.</p>}
    </div>
  );
}
