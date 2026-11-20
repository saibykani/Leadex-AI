"use client";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3, Info, Percent, Target, Users, AlarmClock } from "lucide-react";
import { crm, FUNNEL, STATUSES, statusLabel, type DashboardSummary } from "@/lib/crm";
import { useSession } from "@/lib/session-context";
import { Alert, EmptyState, PageHeader, Skeleton, StatCard } from "@/components/ui";

const GROUPS: { name: string; color: string; statuses: string[] }[] = [
  { name: "Unworked", color: "#8e8e93", statuses: ["discovered", "unverified", "verified", "pending_consent"] },
  { name: "Outreach", color: "#0071e3", statuses: ["approved_for_outreach", "contacted", "callback_requested", "interested"] },
  { name: "Pipeline", color: "#5e5ce6", statuses: ["qualified", "meeting_scheduled", "proposal_sent", "negotiation"] },
  { name: "Won", color: "#1a7f37", statuses: ["converted"] },
  { name: "Closed / opted out", color: "#d70015", statuses: ["lost", "not_interested", "do_not_contact", "suppressed"] },
];
const tip = { borderRadius: 12, border: "1px solid #e5e5ea", fontSize: 13 };

export default function AnalyticsPage() {
  const { can } = useSession();
  const [s, setS] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (can("leads:read")) crm.summary().then(setS).catch((e) => setError(e.message)); }, [can]);

  if (!can("leads:read")) return <div className="space-y-6"><PageHeader title="Analytics" /><EmptyState icon={<BarChart3 className="h-5 w-5" />} title="No access" body="Your role does not include lead analytics." /></div>;

  const n = (k: string) => s?.by_status[k] ?? 0;
  const total = s?.total_leads ?? 0;
  const groups = GROUPS.map((g) => ({ ...g, value: g.statuses.reduce((a, k) => a + n(k), 0) })).filter((g) => g.value > 0);
  // Stage-reached conversion: a lead counts as having reached stage i if it's currently at stage >= i in the funnel.
  const reached = FUNNEL.map((st, i) => ({ label: statusLabel(st), value: FUNNEL.slice(i).reduce((a, k) => a + n(k), 0) }));
  const won = n("converted");
  const closed = won + n("lost") + n("not_interested");
  const all = STATUSES.map((st) => ({ label: statusLabel(st), value: n(st) })).filter((x) => x.value > 0);

  return (
    <div className="space-y-8">
      <PageHeader title="Analytics" description="Live metrics computed from your CRM data." />
      {error && <Alert>{error}</Alert>}
      <div className="flex items-start gap-3 rounded-2xl border border-accent/20 bg-accent/5 p-4 text-sm text-neutral-700">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
        <p>Lead and task analytics are live. Campaign, call, email and revenue analytics will populate here as those modules start recording data — nothing on this page is estimated or simulated.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total leads" value={s?.total_leads} icon={<Users className="h-4 w-4" />} />
        <StatCard label="Win rate (closed)" value={s ? (closed ? `${((won / closed) * 100).toFixed(1)}%` : "—") : undefined} icon={<Percent className="h-4 w-4" />} tone="success" hint="Converted ÷ (converted + lost + not interested)" />
        <StatCard label="Reached outreach" value={s ? reached[2].value : undefined} icon={<Target className="h-4 w-4" />} tone="violet" hint="Approved for outreach or beyond" />
        <StatCard label="Overdue tasks" value={s ? `${s.overdue_tasks} / ${s.open_tasks}` : undefined} icon={<AlarmClock className="h-4 w-4" />} tone={s?.overdue_tasks ? "danger" : "neutral"} hint="Overdue of open" />
      </div>

      {s && total === 0 ? (
        <EmptyState icon={<BarChart3 className="h-5 w-5" />} title="No lead data yet" body="Charts appear once leads exist in this organization." />
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <ChartCard title="Funnel progression" sub="Leads at or beyond each stage">
            {s ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={reached} margin={{ bottom: 40 }}>
                  <CartesianGrid vertical={false} stroke="#e5e5ea" />
                  <XAxis dataKey="label" interval={0} angle={-35} textAnchor="end" tick={{ fontSize: 11, fill: "#6e6e73" }} axisLine={false} tickLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#6e6e73" }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: "#f5f5f7" }} contentStyle={tip} />
                  <Bar dataKey="value" name="Leads" fill="#0071e3" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <Skeleton className="h-full w-full" />}
          </ChartCard>
          <ChartCard title="Pipeline mix" sub="Share of leads by lifecycle group">
            {s ? (
              <div className="flex h-full items-center gap-6">
                <ResponsiveContainer width="55%" height="100%">
                  <PieChart>
                    <Pie data={groups} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="90%" paddingAngle={2} stroke="none">
                      {groups.map((g) => <Cell key={g.name} fill={g.color} />)}
                    </Pie>
                    <Tooltip contentStyle={tip} />
                  </PieChart>
                </ResponsiveContainer>
                <ul className="space-y-2 text-sm">
                  {groups.map((g) => (
                    <li key={g.name} className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: g.color }} />
                      <span className="text-neutral-700">{g.name}</span><span className="ml-auto pl-3 font-medium tabular-nums">{g.value}</span></li>
                  ))}
                </ul>
              </div>
            ) : <Skeleton className="h-full w-full" />}
          </ChartCard>
          <ChartCard title="Leads by status" sub="Every status currently in use" wide>
            {s ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={all} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid horizontal={false} stroke="#e5e5ea" />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12, fill: "#6e6e73" }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="label" width={160} tick={{ fontSize: 12, fill: "#3a3a3c" }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: "#f5f5f7" }} contentStyle={tip} />
                  <Bar dataKey="value" name="Leads" fill="#5e5ce6" radius={[0, 6, 6, 0]} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            ) : <Skeleton className="h-full w-full" />}
          </ChartCard>
        </div>
      )}
    </div>
  );
}

function ChartCard({ title, sub, children, wide }: { title: string; sub: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <section className={`card p-6 ${wide ? "lg:col-span-2" : ""}`}>
      <h2 className="text-[15px] font-semibold">{title}</h2>
      <p className="text-sm text-muted">{sub}</p>
      <div className="mt-4 h-72">{children}</div>
    </section>
  );
}
