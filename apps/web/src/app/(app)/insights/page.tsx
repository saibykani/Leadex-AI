"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3, Bot, Building2, CalendarRange, Coins, Lock, MapPin, Sparkles, Wallet } from "lucide-react";
import { growth, fmtMoney, type Analytics, type Forecast, type Overview, type PipelineValue } from "@/lib/growth";
import { statusLabel } from "@/lib/crm";
import { useSession } from "@/lib/session-context";
import { Alert, Badge, Card, EmptyState, PageHeader, Skeleton, StatCard, Tabs } from "@/components/ui";

const C = { blue: "#0a84ff", indigo: "#5e5ce6", purple: "#bf5af2", green: "#30a46c", amber: "#f59e0b", red: "#e5484d", gray: "#8e8e93" };
const INTEREST_COLORS: Record<string, string> = { high: C.green, medium: C.blue, low: C.amber, none: C.red, unknown: C.gray };
const tip = { contentStyle: { borderRadius: 12, border: "1px solid rgb(var(--c-line))", background: "rgb(var(--c-surface))", fontSize: 12, boxShadow: "var(--shadow-lift)" }, cursor: { fill: "rgb(var(--c-raised))" } };
const axis = { tick: { fontSize: 11, fill: "rgb(var(--c-muted))" }, axisLine: false, tickLine: false } as const;
const day = (d: string) => new Date(d + "T00:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });

export default function InsightsPage() {
  const { can, current } = useSession();
  const [range, setRange] = useState<"30" | "60" | "90">("30");
  const [ov, setOv] = useState<Overview | null>(null);
  const [an, setAn] = useState<Analytics | null>(null);
  const [pv, setPv] = useState<PipelineValue | null>(null);
  const [fc, setFc] = useState<Forecast | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ok = can("leads:read");

  useEffect(() => {
    if (!ok) return;
    setOv(null);
    growth.overview(Number(range)).then(setOv).catch((e) => setError(e.message));
  }, [range, ok, current.organization.id]);
  useEffect(() => {
    if (!ok) return;
    growth.analytics(12).then(setAn).catch((e) => setError(e.message));
    growth.pipelineValue().then(setPv).catch((e) => setError(e.message));
    growth.forecast().then(setFc).catch((e) => setError(e.message));
  }, [ok, current.organization.id]);

  if (!ok) return <EmptyState icon={<Lock className="h-5 w-5" />} title="No access" body="Insights require lead access." />;
  const interest = an ? Object.entries(an.interest).map(([k, v]) => ({ name: k, value: v })) : [];
  const leadsTotal = an ? an.by_industry.reduce((s, r) => s + r.leads, 0) : 0;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Analytics" title="Insights" description="Every chart is computed from your live records — no projections, no sample data."
        actions={<Tabs tabs={[{ id: "30", label: "30d" }, { id: "60", label: "60d" }, { id: "90", label: "90d" }]} value={range} onChange={setRange} />} />
      {error && <Alert>{error}</Alert>}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard label={`Leads · ${range}d`} value={ov?.totals.leads} spark={ov?.points.map((p) => p.leads)} />
        <StatCard label={`Conversions · ${range}d`} value={ov?.totals.conversions} tone="success" spark={ov?.points.map((p) => p.conversions)} sparkColor={C.green} />
        <StatCard label={`Budgets captured · ${range}d`} value={ov?.totals.outcomes_with_budget} tone="violet" spark={ov?.points.map((p) => p.outcomes_with_budget)} sparkColor={C.indigo} />
        <StatCard label={`Websites · ${range}d`} value={ov?.totals.websites} tone="neutral" spark={ov?.points.map((p) => p.websites)} sparkColor={C.purple} />
      </div>

      <Card title="Daily activity" subtitle="Leads created, conversions and AI agent runs per day" icon={<CalendarRange className="h-4 w-4 text-accent" />}>
        <div className="h-72">
          {!ov ? <Skeleton className="h-full w-full" /> : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={ov.points} margin={{ left: -20, right: 8, top: 8 }}>
                <defs>
                  {[["gl", C.blue], ["gc", C.green], ["ga", C.purple]].map(([id, c]) => (
                    <linearGradient key={id} id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={c} stopOpacity={0.3} /><stop offset="1" stopColor={c} stopOpacity={0} /></linearGradient>
                  ))}
                </defs>
                <CartesianGrid vertical={false} stroke="rgb(var(--c-line))" strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={day} minTickGap={24} {...axis} />
                <YAxis allowDecimals={false} {...axis} />
                <Tooltip {...tip} labelFormatter={day} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Area type="monotone" dataKey="leads" name="Leads" stroke={C.blue} strokeWidth={2} fill="url(#gl)" animationDuration={900} />
                <Area type="monotone" dataKey="conversions" name="Conversions" stroke={C.green} strokeWidth={2} fill="url(#gc)" animationDuration={1100} />
                <Area type="monotone" dataKey="agent_runs" name="Agent runs" stroke={C.purple} strokeWidth={2} fill="url(#ga)" animationDuration={1300} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Weekly lead cohorts" subtitle="Leads created each week and how far they progressed" icon={<BarChart3 className="h-4 w-4 text-accent" />}>
          <div className="h-64">
            {!an ? <Skeleton className="h-full w-full" /> : an.cohorts.every((c) => c.created === 0) ? <Empty /> : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={an.cohorts} margin={{ left: -20, right: 8 }}>
                  <CartesianGrid vertical={false} stroke="rgb(var(--c-line))" strokeDasharray="3 3" />
                  <XAxis dataKey="week" tickFormatter={day} {...axis} />
                  <YAxis allowDecimals={false} {...axis} />
                  <Tooltip {...tip} labelFormatter={(w) => `Week of ${day(String(w))}`} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="created" name="Created" fill={C.blue} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="engaged" name="Engaged" fill={C.indigo} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="converted" name="Converted" fill={C.green} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
        <Card title="Outcome interest" subtitle="Interest level across all extracted conversation outcomes" icon={<Sparkles className="h-4 w-4 text-violet-500" />}>
          <div className="h-64">
            {!an ? <Skeleton className="h-full w-full" /> : interest.length === 0 ? <Empty body="Interest appears after AI agent conversations are analysed." /> : (
              <div className="grid h-full grid-cols-[1fr_auto] items-center gap-4">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={interest} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="88%" paddingAngle={3} stroke="none" animationDuration={900}>
                      {interest.map((d) => <Cell key={d.name} fill={INTEREST_COLORS[d.name] ?? C.gray} />)}
                    </Pie>
                    <Tooltip {...tip} />
                  </PieChart>
                </ResponsiveContainer>
                <ul className="space-y-2 pr-2 text-sm">
                  {interest.map((d) => <li key={d.name} className="flex items-center gap-2 capitalize"><span className="h-2.5 w-2.5 rounded-full" style={{ background: INTEREST_COLORS[d.name] ?? C.gray }} />{d.name}<span className="ml-2 tabular-nums text-muted">{d.value}</span></li>)}
                </ul>
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Breakdown title="Conversion by industry" icon={<Building2 className="h-4 w-4 text-accent" />} rows={an?.by_industry} total={leadsTotal} />
        <Breakdown title="Conversion by city" icon={<MapPin className="h-4 w-4 text-accent" />} rows={an?.by_city} total={leadsTotal} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Stated budget distribution" subtitle="Midpoint of each lead's latest stated budget" icon={<Wallet className="h-4 w-4 text-violet-500" />}>
          <div className="h-60">
            {!an ? <Skeleton className="h-full w-full" /> : an.budget_histogram.length === 0 ? <Empty body="No stated budgets captured yet." /> : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={an.budget_histogram.map((b) => ({ ...b, label: `${fmtMoney(b.from, b.currency)}${b.to ? "–" + fmtMoney(b.to, b.currency) : "+"}` }))} margin={{ left: -20, right: 8 }}>
                  <defs><linearGradient id="hb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={C.purple} /><stop offset="1" stopColor={C.indigo} /></linearGradient></defs>
                  <CartesianGrid vertical={false} stroke="rgb(var(--c-line))" strokeDasharray="3 3" />
                  <XAxis dataKey="label" {...axis} interval={0} tick={{ fontSize: 10, fill: "rgb(var(--c-muted))" }} />
                  <YAxis allowDecimals={false} {...axis} />
                  <Tooltip {...tip} />
                  <Bar dataKey="count" name="Leads" fill="url(#hb)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
        <Card title="Forecast & pipeline" subtitle="Transparent formula, real history" icon={<Coins className="h-4 w-4 text-accent" />}>
          {!fc || !pv ? <Skeleton className="h-60 w-full" /> : (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-raised p-3"><div className="text-xs text-muted">Open pipeline</div><div className="mt-1 text-lg font-semibold">{Object.entries(pv.open_value).map(([c, v]) => fmtMoney(v, c)).join(", ") || "—"}</div></div>
                <div className="rounded-xl bg-raised p-3"><div className="text-xs text-muted">Forecast</div><div className="mt-1 text-lg font-semibold">{fc.status === "ok" ? Object.entries(fc.forecast).map(([c, v]) => fmtMoney(v, c)).join(", ") || "—" : <Badge tone="warning">Insufficient data</Badge>}</div></div>
              </div>
              {fc.status === "ok" ? (
                <table className="w-full text-xs">
                  <thead className="text-left text-muted"><tr><th className="py-1 font-medium">Stage</th><th className="font-medium">P(win)</th><th className="text-right font-medium">Weighted</th></tr></thead>
                  <tbody className="divide-y divide-line">
                    {fc.stages.map((s) => <tr key={s.stage}><td className="py-1.5">{statusLabel(s.stage)}</td><td className="tabular-nums">{(s.rate * 100).toFixed(0)}% <span className="text-muted">({s.rate_source}, n={s.sample})</span></td><td className="text-right tabular-nums">{Object.entries(s.weighted).map(([c, v]) => fmtMoney(v, c)).join(", ")}</td></tr>)}
                  </tbody>
                </table>
              ) : <p className="text-muted">{fc.message}</p>}
              <p className="rounded-xl border border-line p-3 font-mono text-[11px] leading-relaxed text-muted">{fc.formula}</p>
            </div>
          )}
        </Card>
      </div>

      <Card title="AI agent outcomes" subtitle="Runs, errors, latency and outcome interest per agent" icon={<Bot className="h-4 w-4 text-accent" />}>
        {!an ? <Skeleton className="h-40 w-full" /> : an.agents.length === 0 ? <Empty body="No agent runs yet. Test an agent to see performance." /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted"><tr><th className="pb-2 font-medium">Agent</th><th className="pb-2 font-medium">Runs</th><th className="pb-2 font-medium">Errors</th><th className="pb-2 font-medium">Avg latency</th><th className="pb-2 font-medium">Outcomes</th></tr></thead>
              <tbody className="divide-y divide-line">
                {an.agents.map((a) => (
                  <tr key={a.agent_id}>
                    <td className="py-2.5 font-medium"><Link href={`/agents/${a.agent_id}`} className="hover:text-accent">{a.name}</Link></td>
                    <td className="tabular-nums">{a.runs}</td>
                    <td className="tabular-nums">{a.errors}</td>
                    <td className="tabular-nums">{a.avg_latency_ms !== null ? `${a.avg_latency_ms} ms` : "—"}</td>
                    <td><div className="flex flex-wrap gap-1">{Object.entries(a.outcomes).map(([k, n]) => <span key={k} className="rounded-full px-2 py-0.5 text-[11px] font-medium capitalize text-white" style={{ background: INTEREST_COLORS[k] ?? C.gray }}>{k} {n}</span>)}{!Object.keys(a.outcomes).length && <span className="text-xs text-muted">—</span>}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {ov && ov.revenue.length > 0 && (
        <Card title="Recorded revenue" subtitle={ov.notes.revenue} icon={<Coins className="h-4 w-4 text-success" />}>
          <ul className="grid gap-3 sm:grid-cols-2">{ov.revenue.map((r) => <li key={r.kind + r.currency} className="rounded-xl bg-raised p-3 text-sm"><div className="text-xs capitalize text-muted">{r.kind.replace(/_/g, " ")}</div><div className="text-lg font-semibold">{fmtMoney(r.total, r.currency)}</div></li>)}</ul>
        </Card>
      )}
    </div>
  );
}

function Empty({ body = "Nothing to show yet." }: { body?: string }) {
  return <div className="grid h-full place-items-center rounded-xl border border-dashed border-line text-center text-sm text-muted"><span className="px-6">{body}</span></div>;
}

function Breakdown({ title, icon, rows, total }: { title: string; icon: React.ReactNode; rows?: Analytics["by_city"]; total: number }) {
  return (
    <Card title={title} subtitle="Lead volume and conversion rate (top 10)" icon={icon}>
      {!rows ? <Skeleton className="h-48 w-full" /> : rows.length === 0 ? <div className="h-48"><Empty /></div> : (
        <ul className="space-y-2.5">
          {rows.map((r) => (
            <li key={r.key} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 text-sm">
              <div className="min-w-0">
                <div className="mb-1 flex justify-between gap-2"><span className="truncate capitalize">{r.key.replace(/_/g, " ")}</span><span className="text-xs tabular-nums text-muted">{r.leads} leads</span></div>
                <div className="h-1.5 overflow-hidden rounded-full bg-raised"><div className="h-full rounded-full bg-brand transition-[width] duration-700" style={{ width: `${total ? (r.leads / total) * 100 : 0}%` }} /></div>
              </div>
              <Badge tone={r.rate > 0 ? "success" : "neutral"} className="w-16 justify-center">{(r.rate * 100).toFixed(0)}%</Badge>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
