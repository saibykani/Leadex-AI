"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Bookmark, ChevronLeft, ChevronRight, Plus, Search, Trash2, Users, X } from "lucide-react";
import { api, type Member, type Page } from "@/lib/api";
import { crm, duplicateLeadId, fmtDate, STATUSES, statusLabel, statusTone, type Lead } from "@/lib/crm";
import { useSession } from "@/lib/session-context";
import { Alert, Badge, Button, Dialog, EmptyState, Input, PageHeader, Select, Skeleton, Table, useToast } from "@/components/ui";

type View = { name: string; q: string; status: string[]; owner: string; sort: string };
const VIEWS_KEY = "lx_lead_views";
function loadViews(): View[] {
  try { return JSON.parse(localStorage.getItem(VIEWS_KEY) ?? "[]") as View[]; } catch { return []; }
}
function saveViews(v: View[]) {
  try { localStorage.setItem(VIEWS_KEY, JSON.stringify(v)); } catch { /* storage unavailable */ }
}
const SORTS = [
  { v: "-created_at", l: "Newest" }, { v: "created_at", l: "Oldest" }, { v: "-updated_at", l: "Recently updated" },
  { v: "business_name", l: "Name A–Z" }, { v: "-business_name", l: "Name Z–A" }, { v: "-score", l: "Highest score" }, { v: "status", l: "Status" },
];
const QUICK = ["discovered", "verified", "approved_for_outreach", "contacted", "interested", "qualified", "meeting_scheduled", "converted", "lost"];
const PAGE_SIZE = 25;

export default function LeadsPage() {
  const { can, current } = useSession();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState<string[]>([]);
  const [owner, setOwner] = useState("");
  const [sort, setSort] = useState("-created_at");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<Lead> | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [views, setViews] = useState<View[]>([]);
  const [creating, setCreating] = useState(false);
  useEffect(() => { if (new URLSearchParams(window.location.search).get("new") === "1" && can("leads:write")) setCreating(true); }, [can]);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => { setViews(loadViews()); }, []);
  useEffect(() => { const t = setTimeout(() => setDebounced(q), 300); return () => clearTimeout(t); }, [q]);
  useEffect(() => { setPage(1); }, [debounced, status, owner, sort]);
  useEffect(() => {
    api<Member[]>(`/organizations/${current.organization.id}/members`).then(setMembers).catch(() => setMembers([]));
  }, [current.organization.id]);

  const load = useCallback(() => {
    setError(null);
    crm.listLeads({ page, page_size: PAGE_SIZE, q: debounced, status, owner: owner || undefined, sort })
      .then(setData).catch((e) => setError(e.message));
  }, [page, debounced, status, owner, sort]);
  useEffect(() => { load(); }, [load]);

  const memberName = useMemo(() => Object.fromEntries(members.map((m) => [m.user_id, m.full_name])), [members]);
  const toggle = (s: string) => setStatus((x) => (x.includes(s) ? x.filter((y) => y !== s) : [...x, s]));
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const filtered = !!(debounced || status.length || owner);

  function saveView() {
    const name = window.prompt("Name this view");
    if (!name?.trim()) return;
    const next = [...views.filter((v) => v.name !== name.trim()), { name: name.trim(), q, status, owner, sort }];
    setViews(next); saveViews(next);
  }
  function applyView(v: View) { setQ(v.q); setDebounced(v.q); setStatus(v.status); setOwner(v.owner); setSort(v.sort); }
  function removeView(name: string) { const next = views.filter((v) => v.name !== name); setViews(next); saveViews(next); }

  return (
    <div className="space-y-6">
      <PageHeader title="Leads" description={data ? `${data.total.toLocaleString()} ${filtered ? "matching" : "total"} leads` : "Your pipeline"}
        actions={can("leads:write") && <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" />New lead</Button>} />

      <div className="card space-y-4 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3.5 top-3 h-4 w-4 text-muted" />
            <Input aria-label="Search leads" placeholder="Search name, email, city, domain…" value={q} onChange={(e) => setQ(e.target.value)} className="h-10 pl-10" />
          </div>
          <Select aria-label="Owner" value={owner} onChange={(e) => setOwner(e.target.value)}>
            <option value="">All owners</option>
            {members.map((m) => <option key={m.user_id} value={m.user_id}>{m.full_name}</option>)}
          </Select>
          <Select aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}>
            {SORTS.map((s) => <option key={s.v} value={s.v}>{s.l}</option>)}
          </Select>
          <Button variant="outline" className="h-10 px-4 text-sm" onClick={saveView}><Bookmark className="h-4 w-4" />Save view</Button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(showAll ? STATUSES : QUICK).map((s) => (
            <button key={s} onClick={() => toggle(s)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition ${status.includes(s) ? "bg-accent text-white" : "bg-raised text-neutral-700 hover:bg-line"}`}>
              {statusLabel(s)}
            </button>
          ))}
          <button onClick={() => setShowAll((x) => !x)} className="px-2 text-xs font-medium text-accent hover:underline">{showAll ? "Fewer" : "All statuses"}</button>
          {filtered && <button onClick={() => { setQ(""); setDebounced(""); setStatus([]); setOwner(""); }} className="ml-auto flex items-center gap-1 text-xs text-muted hover:text-neutral-900"><X className="h-3 w-3" />Clear filters</button>}
        </div>
        {views.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-t border-line pt-3">
            <span className="text-xs text-muted">Saved views:</span>
            {views.map((v) => (
              <span key={v.name} className="inline-flex items-center gap-1 rounded-full border border-line bg-white pl-3 pr-1 text-xs">
                <button onClick={() => applyView(v)} className="py-1 font-medium hover:text-accent">{v.name}</button>
                <button onClick={() => removeView(v.name)} aria-label={`Delete view ${v.name}`} className="rounded-full p-1 text-muted hover:bg-raised"><Trash2 className="h-3 w-3" /></button>
              </span>
            ))}
          </div>
        )}
      </div>

      {error && <Alert>{error}</Alert>}

      {!data ? (
        <div className="card space-y-3 p-5">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
      ) : data.items.length === 0 ? (
        <EmptyState icon={<Users className="h-5 w-5" />} title={filtered ? "No leads match these filters" : "No leads yet"}
          body={filtered ? "Try a different search or clear filters." : "Create a lead manually or import businesses from Discovery."} />
      ) : (
        <>
          <Table head={["Business", "Status", "Location", "Contact", "Score", "Owner", "Created"]}>
            {data.items.map((l) => (
              <tr key={l.id} onClick={() => router.push(`/leads/${l.id}`)} className="cursor-pointer transition-colors hover:bg-raised/60">
                <td className="px-5 py-3.5">
                  <Link href={`/leads/${l.id}`} onClick={(e) => e.stopPropagation()} className="font-medium hover:text-accent">{l.business_name}</Link>
                  {l.industry && <div className="text-xs text-muted">{l.industry}</div>}
                </td>
                <td className="px-5 py-3.5"><Badge tone={statusTone(l.status)}>{statusLabel(l.status)}</Badge></td>
                <td className="whitespace-nowrap px-5 py-3.5 text-muted">{[l.city, l.country].filter(Boolean).join(", ") || "—"}</td>
                <td className="px-5 py-3.5 text-muted"><div className="max-w-[200px] truncate">{l.email ?? l.phone ?? "—"}</div></td>
                <td className="px-5 py-3.5 tabular-nums">{l.score ?? "—"}</td>
                <td className="whitespace-nowrap px-5 py-3.5 text-muted">{l.owner_user_id ? memberName[l.owner_user_id] ?? "Unknown" : "Unassigned"}</td>
                <td className="whitespace-nowrap px-5 py-3.5 text-muted">{fmtDate(l.created_at)}</td>
              </tr>
            ))}
          </Table>
          <div className="flex items-center justify-between text-sm text-muted">
            <span>Page {data.page} of {pages}</span>
            <div className="flex gap-2">
              <Button variant="outline" className="h-9 px-3" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></Button>
              <Button variant="outline" className="h-9 px-3" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></Button>
            </div>
          </div>
        </>
      )}

      <CreateLeadDialog open={creating} onClose={() => setCreating(false)} members={members}
        onCreated={(l) => { setCreating(false); router.push(`/leads/${l.id}`); }} />
    </div>
  );
}

const schema = z.object({
  business_name: z.string().trim().min(1, "Business name is required").max(300),
  industry: z.string().max(120).optional(),
  email: z.union([z.literal(""), z.string().email("Invalid email")]).optional(),
  phone: z.string().max(40).optional(),
  website: z.string().max(500).optional(),
  city: z.string().max(120).optional(),
  country: z.union([z.literal(""), z.string().regex(/^[A-Za-z]{2}$/, "Use a 2-letter code")]).optional(),
  score: z.union([z.literal(""), z.coerce.number().int().min(0).max(100)]).optional(),
  owner_user_id: z.string().optional(),
});
type Form = z.infer<typeof schema>;
const blankToNull = (v: unknown) => (v === "" || v === undefined ? null : v);

function CreateLeadDialog({ open, onClose, onCreated, members }: { open: boolean; onClose: () => void; onCreated: (l: Lead) => void; members: Member[] }) {
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const [dupId, setDupId] = useState<string | null>(null);
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema) });
  useEffect(() => { if (open) { reset(); setError(null); setDupId(null); } }, [open, reset]);

  async function submit(f: Form) {
    setError(null); setDupId(null);
    try {
      const lead = await crm.createLead({
        business_name: f.business_name, industry: blankToNull(f.industry) as string | null, email: blankToNull(f.email) as string | null,
        phone: blankToNull(f.phone) as string | null, website: blankToNull(f.website) as string | null, city: blankToNull(f.city) as string | null,
        country: f.country ? f.country.toUpperCase() : null, score: blankToNull(f.score) as number | null,
        owner_user_id: blankToNull(f.owner_user_id) as string | null, source: "manual",
      });
      toast("Lead created", "success");
      onCreated(lead);
    } catch (e) {
      setDupId(duplicateLeadId(e));
      setError((e as Error).message);
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="New lead" description="Leads start as Discovered and move through the compliance lifecycle." wide
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button type="submit" form="create-lead" loading={isSubmitting}>Create lead</Button></>}>
      <form id="create-lead" onSubmit={handleSubmit(submit)} className="grid gap-4 sm:grid-cols-2">
        {error && (
          <div className="sm:col-span-2"><Alert>{error}{dupId && <> — <Link href={`/leads/${dupId}`} className="font-medium underline">open existing lead</Link></>}</Alert></div>
        )}
        <div className="sm:col-span-2"><label className="label" htmlFor="bn">Business name</label><Input id="bn" autoFocus {...register("business_name")} error={errors.business_name?.message} /></div>
        <div><label className="label" htmlFor="ind">Industry</label><Input id="ind" {...register("industry")} /></div>
        <div><label className="label" htmlFor="own">Owner</label>
          <Select id="own" className="h-12 w-full" {...register("owner_user_id")}>
            <option value="">Unassigned</option>
            {members.map((m) => <option key={m.user_id} value={m.user_id}>{m.full_name}</option>)}
          </Select></div>
        <div><label className="label" htmlFor="em">Email</label><Input id="em" type="email" {...register("email")} error={errors.email?.message} /></div>
        <div><label className="label" htmlFor="ph">Phone</label><Input id="ph" {...register("phone")} /></div>
        <div className="sm:col-span-2"><label className="label" htmlFor="ws">Website</label><Input id="ws" placeholder="example.com" {...register("website")} /></div>
        <div><label className="label" htmlFor="ci">City</label><Input id="ci" {...register("city")} /></div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label" htmlFor="co">Country</label><Input id="co" maxLength={2} placeholder="US" {...register("country")} error={errors.country?.message} /></div>
          <div><label className="label" htmlFor="sc">Score</label><Input id="sc" type="number" min={0} max={100} {...register("score")} error={errors.score?.message} /></div>
        </div>
      </form>
    </Dialog>
  );
}
