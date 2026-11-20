"use client";
import Link from "next/link";
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, ExternalLink, Search, ShieldAlert, Check } from "lucide-react";
import { useSession } from "@/lib/session-context";
import { api, ApiError, type Member, type Page } from "@/lib/api";
import { Alert, Badge, Button, Input, Select, Table, Tabs, Textarea, Skeleton, type Tone } from "@/components/ui";

type Status = "new" | "contacted" | "qualified" | "closed";
type Inquiry = {
  id: string; reference: string; type: string; status: Status; name: string; email: string;
  company: string | null; role: string | null; team_size: string | null; country: string | null; phone: string | null;
  interests: string[]; message: string | null; preferred_time: string | null; timezone: string | null;
  marketing_consent: boolean; booking_start: string | null; lead_id: string | null;
  assignee_user_id: string | null; created_at: string;
};
type PlanDisplay = {
  code: string; name: string; trial_days: number; price_monthly: string | null; price_annual: string | null;
  currency: string; contact_sales: boolean; highlight: boolean; badge: string | null; tagline: string | null;
  bullets: string[]; limits: Record<string, unknown>; features: string[];
};
type Draft = {
  plan_code: string; name: string; trial_days: number; price_monthly: string; price_annual: string; currency: string;
  contact_sales: boolean; highlight: boolean; badge: string; tagline: string; bullets: string;
};
type Settings = {
  timezone: string; weekdays: number[]; day_start: string; day_end: string; slot_minutes: number;
  buffer_minutes: number; min_notice_hours: number; horizon_days: number; booking_enabled: boolean;
};
type SettingsResp = { settings: Settings; warnings: string[]; platform_owner_org_id: string | null; is_platform_owner_context: boolean };

const STATUSES: Status[] = ["new", "contacted", "qualified", "closed"];
const STATUS_TONE: Record<Status, Tone> = { new: "accent", contacted: "warning", qualified: "success", closed: "neutral" };
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const fmt = (s: string | null) => (s ? new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
const msg = (e: unknown) => (e as Error).message || "Something went wrong";
const isForbidden = (e: unknown) => e instanceof ApiError && (e.status === 403 || e.code === "forbidden");

function Forbidden() {
  return (
    <div className="card flex flex-col items-center gap-3 p-8 text-center">
      <ShieldAlert className="h-8 w-8 text-muted" />
      <h2 className="text-lg font-semibold">Sales console is for the platform owner</h2>
      <p className="max-w-md text-sm text-muted">
        This workspace isn&apos;t the LEADEX AI platform-owner organization, so it can&apos;t see public sales inquiries,
        edit public pricing or manage demo availability. Switch to the platform-owner organization to use it.
      </p>
    </div>
  );
}

export default function SalesPage() {
  const { current } = useSession();
  const [tab, setTab] = useState<"inbox" | "pricing" | "availability">("inbox");
  const [forbidden, setForbidden] = useState(false);
  const deny = useCallback(() => setForbidden(true), []);
  useEffect(() => setForbidden(false), [current.organization.id]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Sales console</h1>
        <p className="text-sm text-muted">Inquiries from the public site, public pricing display and demo booking availability.</p>
      </div>
      {forbidden ? <Forbidden /> : (
        <>
          <Tabs value={tab} onChange={setTab} tabs={[
            { id: "inbox", label: "Inbox" }, { id: "pricing", label: "Pricing" }, { id: "availability", label: "Availability" },
          ]} />
          {tab === "inbox" && <Inbox orgId={current.organization.id} onForbidden={deny} />}
          {tab === "pricing" && <Pricing orgId={current.organization.id} onForbidden={deny} />}
          {tab === "availability" && <Availability orgId={current.organization.id} onForbidden={deny} />}
        </>
      )}
    </div>
  );
}

/* ---------------- Inbox ---------------- */
function Inbox({ orgId, onForbidden }: { orgId: string; onForbidden: () => void }) {
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<Inquiry> | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 25;

  useEffect(() => { const t = setTimeout(() => { setQuery(q); setPage(1); }, 300); return () => clearTimeout(t); }, [q]);

  const load = useCallback(() => {
    setError(null);
    const p = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (status) p.set("status", status);
    if (type) p.set("type", type);
    if (query) p.set("q", query);
    api<Page<Inquiry>>(`/sales/inquiries?${p}`, {}, true)
      .then(setData)
      .catch((e) => (isForbidden(e) ? onForbidden() : setError(msg(e))));
  }, [status, type, query, page, onForbidden, orgId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(load, [load]);
  useEffect(() => {
    api<Member[]>(`/organizations/${orgId}/members`, {}, true).then(setMembers).catch(() => setMembers([]));
  }, [orgId]);

  const patch = async (id: string, body: Record<string, unknown>) => {
    try {
      const updated = await api<Inquiry>(`/sales/inquiries/${id}`, { method: "PATCH", body: JSON.stringify(body) }, true);
      setData((d) => d && { ...d, items: d.items.map((i) => (i.id === id ? { ...i, ...updated } : i)) });
    } catch (e) { setError(msg(e)); }
  };
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="space-y-4">
      {error && <Alert>{error}</Alert>}
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, email, company, reference" className="h-10 pl-9 text-sm" />
        </div>
        <div className="grid grid-cols-2 gap-2 sm:flex">
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="sm:w-40" aria-label="Status">
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
          </Select>
          <Select value={type} onChange={(e) => { setType(e.target.value); setPage(1); }} className="sm:w-40" aria-label="Type">
            <option value="">All types</option>
            {[["talk_to_sales","Talk to sales"],["demo_request","Demo request"],["partnership","Partnership"],["support","Support"],["general","General"]].map(([v,l]) => <option key={v} value={v}>{l}</option>)}
          </Select>
        </div>
      </div>

      {!data ? <Skeleton className="h-64" /> : data.items.length === 0 ? (
        <div className="card p-8 text-center text-sm text-muted">No inquiries match these filters.</div>
      ) : (
        <Table head={["", "Reference", "Received", "Type", "Contact", "Booking", "Status", "Assignee", ""]}>
          {data.items.map((i) => (
            <Fragment key={i.id}>
              <tr>
                <td className="px-3 py-3">
                  <button aria-label="Toggle details" onClick={() => setOpen(open === i.id ? null : i.id)} className="rounded p-1 text-muted hover:text-ink">
                    {open === i.id ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </button>
                </td>
                <td className="whitespace-nowrap px-5 py-3 font-mono text-xs">{i.reference}</td>
                <td className="whitespace-nowrap px-5 py-3 text-muted">{fmt(i.created_at)}</td>
                <td className="px-5 py-3"><Badge tone={i.type === "demo_request" ? "violet" : "neutral"}>{i.type.replace(/_/g, " ")}</Badge></td>
                <td className="min-w-[200px] px-5 py-3">
                  <div className="font-medium">{i.name}{i.company && <span className="text-muted"> · {i.company}</span>}</div>
                  <a href={`mailto:${i.email}`} className="text-xs text-accent hover:underline">{i.email}</a>
                </td>
                <td className="whitespace-nowrap px-5 py-3">{i.booking_start ? fmt(i.booking_start) : <span className="text-muted">—</span>}</td>
                <td className="px-5 py-3">
                  <Select value={i.status} onChange={(e) => patch(i.id, { status: e.target.value })} className="h-9 w-32" aria-label="Status">
                    {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </Select>
                </td>
                <td className="px-5 py-3">
                  <Select value={i.assignee_user_id ?? ""} aria-label="Assignee" className="h-9 w-44"
                    onChange={(e) => patch(i.id, e.target.value ? { assignee_user_id: e.target.value } : { clear_assignee: true })}>
                    <option value="">Unassigned</option>
                    {members.map((m) => <option key={m.user_id} value={m.user_id}>{m.full_name || m.email}</option>)}
                  </Select>
                </td>
                <td className="whitespace-nowrap px-5 py-3">
                  {i.lead_id ? (
                    <Link href={`/leads/${i.lead_id}`} className="inline-flex items-center gap-1 text-accent hover:underline">
                      Open lead <ExternalLink className="h-3.5 w-3.5" />
                    </Link>
                  ) : <span className="text-xs text-muted">No lead</span>}
                </td>
              </tr>
              {open === i.id && (
                <tr className="bg-raised/30">
                  <td colSpan={9} className="px-5 py-4">
                    <div className="grid gap-4 text-sm md:grid-cols-3">
                      <div className="md:col-span-2">
                        <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Message</div>
                        <p className="whitespace-pre-wrap">{i.message || <span className="text-muted">No message</span>}</p>
                        {i.interests.length > 0 && (
                          <div className="mt-3 flex flex-wrap gap-1.5">{i.interests.map((x) => <Badge key={x} tone="accent">{x}</Badge>)}</div>
                        )}
                      </div>
                      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                        <dt className="text-muted">Marketing consent</dt>
                        <dd><Badge tone={i.marketing_consent ? "success" : "danger"} dot>{i.marketing_consent ? "Yes — opted in" : "No — do not market"}</Badge></dd>
                        <dt className="text-muted">Role</dt><dd>{i.role || "—"}</dd>
                        <dt className="text-muted">Team size</dt><dd>{i.team_size || "—"}</dd>
                        <dt className="text-muted">Country</dt><dd>{i.country || "—"}</dd>
                        <dt className="text-muted">Phone</dt><dd>{i.phone || "—"}</dd>
                        <dt className="text-muted">Preferred time</dt><dd>{i.preferred_time || "—"}</dd>
                        <dt className="text-muted">Timezone</dt><dd>{i.timezone || "—"}</dd>
                      </dl>
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </Table>
      )}
      {data && pages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted">
          <span>{data.total} inquiries</span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
            <span>{page} / {pages}</span>
            <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------- Pricing ---------------- */
const toDraft = (p: PlanDisplay): Draft => ({
  plan_code: p.code, name: p.name, trial_days: p.trial_days, price_monthly: p.price_monthly ?? "", price_annual: p.price_annual ?? "",
  currency: p.currency || "USD", contact_sales: p.contact_sales, highlight: p.highlight, badge: p.badge ?? "",
  tagline: p.tagline ?? "", bullets: (p.bullets ?? []).join("\n"),
});
const num = (s: string) => (s.trim() === "" ? null : Number(s));
const priceLabel = (v: string, cur: string) => {
  const n = num(v);
  if (n === null || Number.isNaN(n)) return null;
  try { return new Intl.NumberFormat(undefined, { style: "currency", currency: cur || "USD", maximumFractionDigits: n % 1 ? 2 : 0 }).format(n); }
  catch { return `${cur} ${n}`; }
};

function Pricing({ orgId, onForbidden }: { orgId: string; onForbidden: () => void }) {
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setDrafts(null); setError(null);
    api<{ plans: PlanDisplay[] }>("/sales/plan-display", {}, true)
      .then((r) => setDrafts(r.plans.map(toDraft)))
      .catch((e) => (isForbidden(e) ? onForbidden() : setError(msg(e))));
  }, [orgId, onForbidden]);

  const set = (i: number, patch: Partial<Draft>) => setDrafts((d) => d && d.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  const invalid = useMemo(() => (drafts ?? []).some((d) => [d.price_monthly, d.price_annual].some((v) => { const n = num(v); return n !== null && (Number.isNaN(n) || n < 0); })), [drafts]);

  const save = async () => {
    if (!drafts) return;
    setBusy(true); setError(null); setNote(null);
    try {
      const r = await api<{ plans: PlanDisplay[] }>("/sales/plan-display", {
        method: "PUT",
        body: JSON.stringify({
          items: drafts.map((d) => ({
            plan_code: d.plan_code, price_monthly: num(d.price_monthly), price_annual: num(d.price_annual),
            currency: d.currency.trim().toUpperCase() || "USD", contact_sales: d.contact_sales, highlight: d.highlight,
            badge: d.badge.trim() || null, tagline: d.tagline.trim() || null,
            bullets: d.bullets.split("\n").map((b) => b.trim()).filter(Boolean),
          })),
        }),
      }, true);
      if (r?.plans) setDrafts(r.plans.map(toDraft));
      setNote("Public pricing saved.");
    } catch (e) { setError(msg(e)); } finally { setBusy(false); }
  };

  if (!drafts) return error ? <Alert>{error}</Alert> : <Skeleton className="h-96" />;
  return (
    <div className="space-y-4">
      <Alert tone="info">
        Leave a price empty to show &ldquo;Contact sales&rdquo; publicly. Prices shown on the public site come only from these
        fields — nothing is ever invented or estimated. Annual price is the per-month amount when billed yearly.
      </Alert>
      {error && <Alert>{error}</Alert>}
      {note && <Alert tone="success">{note}</Alert>}
      {drafts.map((d, i) => (
        <div key={d.plan_code} className="card grid gap-6 p-4 sm:p-6 lg:grid-cols-[1fr_320px]">
          <div className="space-y-3">
            <div className="flex items-baseline justify-between gap-2">
              <h3 className="font-semibold">{d.name}</h3>
              <span className="font-mono text-xs text-muted">{d.plan_code}</span>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Field label="Monthly price"><Input inputMode="decimal" value={d.price_monthly} placeholder="Contact sales" onChange={(e) => set(i, { price_monthly: e.target.value })} className="h-10 text-sm" /></Field>
              <Field label="Annual (per month)"><Input inputMode="decimal" value={d.price_annual} placeholder="Contact sales" onChange={(e) => set(i, { price_annual: e.target.value })} className="h-10 text-sm" /></Field>
              <Field label="Currency"><Input value={d.currency} maxLength={3} onChange={(e) => set(i, { currency: e.target.value.toUpperCase() })} className="h-10 text-sm uppercase" /></Field>
            </div>
            <div className="flex flex-wrap gap-4">
              <Toggle label="Contact sales" checked={d.contact_sales} onChange={(v) => set(i, { contact_sales: v })} />
              <Toggle label="Highlight" checked={d.highlight} onChange={(v) => set(i, { highlight: v })} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Badge"><Input value={d.badge} placeholder="e.g. Most popular" onChange={(e) => set(i, { badge: e.target.value })} className="h-10 text-sm" /></Field>
              <Field label="Tagline"><Input value={d.tagline} onChange={(e) => set(i, { tagline: e.target.value })} className="h-10 text-sm" /></Field>
            </div>
            <Field label="Bullets (one per line)"><Textarea rows={4} value={d.bullets} onChange={(e) => set(i, { bullets: e.target.value })} /></Field>
          </div>
          <Preview d={d} />
        </div>
      ))}
      <div className="flex items-center justify-end gap-3">
        {invalid && <span className="text-sm text-danger">Prices must be non-negative numbers.</span>}
        <Button onClick={save} loading={busy} disabled={invalid}>Save all</Button>
      </div>
    </div>
  );
}

function Preview({ d }: { d: Draft }) {
  const monthly = priceLabel(d.price_monthly, d.currency);
  const annual = priceLabel(d.price_annual, d.currency);
  const showPrice = !d.contact_sales && monthly !== null;
  const bullets = d.bullets.split("\n").map((b) => b.trim()).filter(Boolean);
  const card = (
    <div className="relative h-full rounded-[22px] bg-white p-6 text-[#1d1d1f] shadow-[0_8px_30px_rgba(0,0,0,0.08)]">
      {d.badge && (
        <span className="absolute right-4 top-4 rounded-full bg-[#0071e3]/10 px-2.5 py-0.5 text-[11px] font-semibold text-[#0071e3]">{d.badge}</span>
      )}
      <div className="text-lg font-semibold">{d.name}</div>
      {d.tagline && <p className="mt-1 text-sm text-[#6e6e73]">{d.tagline}</p>}
      <div className="mt-4">
        {showPrice ? (
          <>
            <span className="text-3xl font-semibold tracking-tight">{monthly}</span><span className="text-sm text-[#6e6e73]"> /mo</span>
            {annual && <div className="text-xs text-[#6e6e73]">{annual}/mo billed annually</div>}
          </>
        ) : <span className="text-2xl font-semibold tracking-tight">Contact sales</span>}
      </div>
      {d.trial_days > 0 && <div className="mt-1 text-xs text-[#6e6e73]">{d.trial_days}-day free trial</div>}
      <ul className="mt-4 space-y-2 text-sm">
        {bullets.map((b) => <li key={b} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-[#0071e3]" />{b}</li>)}
      </ul>
      <div className={`mt-5 rounded-full py-2 text-center text-sm font-medium ${d.highlight ? "bg-[#0071e3] text-white" : "border border-[#0071e3] text-[#0071e3]"}`}>
        {showPrice ? "Start free trial" : "Talk to sales"}
      </div>
    </div>
  );
  return (
    <div>
      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Live preview</div>
      <div className="rounded-3xl bg-[#f5f5f7] p-4">
        {d.highlight ? <div className="rounded-[24px] bg-gradient-to-br from-[#0a84ff] via-[#5e5ce6] to-[#bf5af2] p-[2px]">{card}</div> : card}
      </div>
    </div>
  );
}

/* ---------------- Availability ---------------- */
function Availability({ orgId, onForbidden }: { orgId: string; onForbidden: () => void }) {
  const [data, setData] = useState<SettingsResp | null>(null);
  const [s, setS] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setData(null); setS(null); setError(null);
    api<SettingsResp>("/sales/settings", {}, true)
      .then((r) => { setData(r); setS(r.settings); })
      .catch((e) => (isForbidden(e) ? onForbidden() : setError(msg(e))));
  }, [orgId, onForbidden]);

  const save = async () => {
    if (!s) return;
    setBusy(true); setError(null); setNote(null);
    try {
      const r = await api<{ settings: Settings }>("/sales/settings", { method: "PUT", body: JSON.stringify(s) }, true);
      setS(r.settings); setNote("Availability saved.");
    } catch (e) { setError(msg(e)); } finally { setBusy(false); }
  };

  if (!s || !data) return error ? <Alert>{error}</Alert> : <Skeleton className="h-80" />;
  const up = (p: Partial<Settings>) => setS({ ...s, ...p });
  const n = (k: keyof Settings) => (e: React.ChangeEvent<HTMLInputElement>) => up({ [k]: Number(e.target.value) } as Partial<Settings>);
  return (
    <div className="space-y-4">
      {data.warnings.map((w) => <Alert key={w}>{w}</Alert>)}
      {!data.is_platform_owner_context && data.platform_owner_org_id && (
        <Alert tone="info">You are not in the platform-owner organization; inquiries are routed to a different workspace.</Alert>
      )}
      {error && <Alert>{error}</Alert>}
      {note && <Alert tone="success">{note}</Alert>}
      <div className="card space-y-5 p-4 sm:p-6">
        <Toggle label="Online demo booking enabled" checked={s.booking_enabled} onChange={(v) => up({ booking_enabled: v })} />
        <Field label="Timezone (IANA, e.g. Europe/London)"><Input value={s.timezone} onChange={(e) => up({ timezone: e.target.value })} className="h-10 text-sm" /></Field>
        <div>
          <div className="mb-1.5 text-xs font-medium text-muted">Working days</div>
          <div className="flex flex-wrap gap-2">
            {DAYS.map((label, d) => {
              const on = s.weekdays.includes(d);
              return (
                <button key={label} type="button" aria-pressed={on}
                  onClick={() => up({ weekdays: on ? s.weekdays.filter((x) => x !== d) : [...s.weekdays, d].sort() })}
                  className={`h-9 w-12 rounded-full text-sm font-medium transition-colors ${on ? "bg-accent text-white" : "bg-raised text-muted hover:text-ink"}`}>
                  {label}
                </button>
              );
            })}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Field label="Day start"><Input type="time" value={s.day_start} onChange={(e) => up({ day_start: e.target.value })} className="h-10 text-sm" /></Field>
          <Field label="Day end"><Input type="time" value={s.day_end} onChange={(e) => up({ day_end: e.target.value })} className="h-10 text-sm" /></Field>
          <Field label="Slot length (min)"><Input type="number" min={5} value={s.slot_minutes} onChange={n("slot_minutes")} className="h-10 text-sm" /></Field>
          <Field label="Buffer (min)"><Input type="number" min={0} value={s.buffer_minutes} onChange={n("buffer_minutes")} className="h-10 text-sm" /></Field>
          <Field label="Minimum notice (hours)"><Input type="number" min={0} value={s.min_notice_hours} onChange={n("min_notice_hours")} className="h-10 text-sm" /></Field>
          <Field label="Booking horizon (days)"><Input type="number" min={1} value={s.horizon_days} onChange={n("horizon_days")} className="h-10 text-sm" /></Field>
        </div>
        {s.day_start >= s.day_end && <p className="text-sm text-danger">Day end must be after day start.</p>}
        <div className="flex justify-end">
          <Button onClick={save} loading={busy} disabled={s.day_start >= s.day_end}>Save availability</Button>
        </div>
      </div>
    </div>
  );
}

/* ---------------- helpers ---------------- */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block"><span className="mb-1 block text-xs font-medium text-muted">{label}</span>{children}</label>;
}
function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className="inline-flex items-center gap-2 text-sm">
      <span className={`relative h-6 w-10 rounded-full transition-colors ${checked ? "bg-accent" : "bg-line"}`}>
        <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${checked ? "left-[18px]" : "left-0.5"}`} />
      </span>
      {label}
    </button>
  );
}
