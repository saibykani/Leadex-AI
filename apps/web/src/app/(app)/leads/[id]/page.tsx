"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft, Building2, CalendarClock, CheckCircle2, Circle, Globe, Mail, MapPin, MessageSquare, Pencil, Phone, Plus, ShieldCheck, Trash2,
} from "lucide-react";
import { api, type Member, type Page } from "@/lib/api";
import {
  allowedNext, CONSENT_REQUIRED, crm, duplicateLeadId, fmtDateTime, STATUSES, statusLabel, statusTone, timeAgo,
  type Activity, type Lead, type LeadInput, type LeadStatus, type Note, type Task,
} from "@/lib/crm";
import { useSession } from "@/lib/session-context";
import { LeadActions } from "@/components/lead-actions";
import {
  Alert, Badge, Button, ConfirmDialog, Dialog, Input, Select, Skeleton, Tabs, Textarea, useToast,
} from "@/components/ui";

export default function LeadDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const { can, current } = useSession();
  const canWrite = can("leads:write");
  const [lead, setLead] = useState<Lead | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [acts, setActs] = useState<Page<Activity> | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"activity" | "notes" | "tasks">("activity");
  const [statusOpen, setStatusOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const refreshSide = useCallback(() => {
    crm.notes(id).then(setNotes).catch(() => {});
    crm.tasks(id).then(setTasks).catch(() => {});
    crm.activities(id).then(setActs).catch(() => {});
  }, [id]);
  useEffect(() => {
    crm.getLead(id).then(setLead).catch((e) => setError(e.message));
    refreshSide();
    api<Member[]>(`/organizations/${current.organization.id}/members`).then(setMembers).catch(() => {});
  }, [id, current.organization.id, refreshSide]);
  const names = useMemo(() => Object.fromEntries(members.map((m) => [m.user_id, m.full_name])), [members]);
  const onLead = (l: Lead) => { setLead(l); refreshSide(); };

  if (error && !lead) return <div className="space-y-4"><BackLink /><Alert>{error}</Alert></div>;
  if (!lead) return <div className="space-y-4"><BackLink /><Skeleton className="h-28 w-full" /><Skeleton className="h-64 w-full" /></div>;

  const openTasks = tasks.filter((t) => !t.completed_at).length;
  return (
    <div className="space-y-6">
      <BackLink />
      <div className="card flex flex-wrap items-start justify-between gap-4 p-6">
        <div className="flex min-w-0 items-start gap-4">
          <div className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent"><Building2 className="h-6 w-6" /></div>
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-semibold tracking-tight">{lead.business_name}</h1>
            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-muted">
              <Badge tone={statusTone(lead.status)}>{statusLabel(lead.status)}</Badge>
              {lead.industry && <span>{lead.industry}</span>}
              <span>· Source: {lead.source}</span>
              {lead.consent_reference && <span className="inline-flex items-center gap-1 text-success"><ShieldCheck className="h-3.5 w-3.5" />Consent on file</span>}
            </div>
          </div>
        </div>
        {canWrite && (
          <div className="flex flex-wrap gap-2">
            <LeadActions leadId={lead.id} onChange={() => { crm.getLead(id).then(onLead).catch(() => {}); }} />
            <Button onClick={() => setStatusOpen(true)}>Change status</Button>
            <Button variant="outline" onClick={() => setEditing(true)}><Pencil className="h-4 w-4" />Edit</Button>
            <Button variant="ghost" onClick={() => setDeleting(true)} aria-label="Delete lead"><Trash2 className="h-4 w-4" /></Button>
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <aside className="card h-fit space-y-4 p-6">
          <h2 className="text-[15px] font-semibold">Details</h2>
          <Field icon={<Mail className="h-4 w-4" />} label="Email" value={lead.email && <a href={`mailto:${lead.email}`} className="text-accent hover:underline">{lead.email}</a>} />
          <Field icon={<Phone className="h-4 w-4" />} label="Phone" value={lead.phone} />
          <Field icon={<Globe className="h-4 w-4" />} label="Website" value={lead.website && <a href={/^https?:\/\//.test(lead.website) ? lead.website : `https://${lead.website}`} target="_blank" rel="noreferrer noopener" className="text-accent hover:underline">{lead.website}</a>} />
          <Field icon={<MapPin className="h-4 w-4" />} label="Location" value={[lead.city, lead.country].filter(Boolean).join(", ")} />
          <div className="grid grid-cols-2 gap-4 border-t border-line pt-4 text-sm">
            <div><div className="text-xs text-muted">Score</div><div className="mt-0.5 font-medium">{lead.score ?? "—"}</div></div>
            <div><div className="text-xs text-muted">Owner</div><div className="mt-0.5 font-medium">{lead.owner_user_id ? names[lead.owner_user_id] ?? "Unknown" : "Unassigned"}</div></div>
            <div><div className="text-xs text-muted">Created</div><div className="mt-0.5">{fmtDateTime(lead.created_at)}</div></div>
            <div><div className="text-xs text-muted">Updated</div><div className="mt-0.5">{fmtDateTime(lead.updated_at)}</div></div>
          </div>
          {lead.consent_reference && <div className="rounded-xl bg-success/5 p-3 text-xs text-success">Consent reference: <span className="font-mono">{lead.consent_reference}</span></div>}
        </aside>

        <section className="space-y-4 lg:col-span-2">
          <Tabs value={tab} onChange={setTab} tabs={[
            { id: "activity", label: "Activity" }, { id: "notes", label: `Notes${notes.length ? ` · ${notes.length}` : ""}` },
            { id: "tasks", label: `Tasks${openTasks ? ` · ${openTasks}` : ""}` },
          ]} />
          {tab === "activity" && <Timeline acts={acts} names={names} />}
          {tab === "notes" && <Notes leadId={id} notes={notes} names={names} canWrite={canWrite} onChange={refreshSide} />}
          {tab === "tasks" && <Tasks leadId={id} tasks={tasks} members={members} names={names} canWrite={canWrite} onChange={refreshSide} />}
        </section>
      </div>

      <StatusDialog open={statusOpen} onClose={() => setStatusOpen(false)} lead={lead}
        isAdmin={["Owner", "Admin"].includes(current.role)} onDone={(l) => { setStatusOpen(false); onLead(l); toast("Status updated", "success"); }} />
      <EditDialog open={editing} onClose={() => setEditing(false)} lead={lead} members={members}
        onDone={(l) => { setEditing(false); onLead(l); toast("Lead saved", "success"); }} />
      <DeleteLead open={deleting} onClose={() => setDeleting(false)} lead={lead} onDone={() => { toast("Lead deleted", "success"); router.push("/leads"); }} />
    </div>
  );
}

function BackLink() {
  return <Link href="/leads" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-neutral-900"><ArrowLeft className="h-4 w-4" />All leads</Link>;
}
function Field({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 text-sm">
      <span className="mt-0.5 text-muted">{icon}</span>
      <div className="min-w-0"><div className="text-xs text-muted">{label}</div><div className="break-words">{value || <span className="text-neutral-400">—</span>}</div></div>
    </div>
  );
}

function describe(a: Activity): string {
  const d = a.data ?? {};
  switch (a.type) {
    case "lead.created": return "created this lead";
    case "status.changed": return `changed status from ${statusLabel(String(d.from))} to ${statusLabel(String(d.to))}${d.admin_override ? " (admin override)" : ""}`;
    case "lead.updated": return `updated ${Object.keys((d.changes as object) ?? {}).map((k) => k.replace(/_/g, " ")).join(", ") || "fields"}`;
    case "note.added": return "added a note";
    case "task.created": return `created task “${String(d.title ?? "")}”`;
    case "task.completed": return "completed a task";
    case "task.updated": return "updated a task";
    case "lead.deleted": return "deleted this lead";
    default: return a.type.replace(/[._]/g, " ");
  }
}
function Timeline({ acts, names }: { acts: Page<Activity> | null; names: Record<string, string> }) {
  if (!acts) return <Skeleton className="h-40 w-full" />;
  if (!acts.items.length) return <div className="card p-8 text-center text-sm text-muted">No activity yet.</div>;
  return (
    <ol className="card relative space-y-0 p-6">
      {acts.items.map((a, i) => (
        <li key={a.id} className="relative flex gap-4 pb-5 last:pb-0">
          {i < acts.items.length - 1 && <span className="absolute left-[7px] top-5 h-full w-px bg-line" />}
          <span className="relative mt-1 h-[15px] w-[15px] shrink-0 rounded-full border-[3px] border-white bg-accent ring-1 ring-accent/30" />
          <div className="min-w-0 text-sm">
            <span className="font-medium">{a.actor_user_id ? names[a.actor_user_id] ?? "Someone" : "System"}</span> {describe(a)}
            {typeof a.data?.reason === "string" && <div className="mt-0.5 text-xs text-muted">Reason: {a.data.reason}</div>}
            <div className="mt-0.5 text-xs text-muted" title={new Date(a.created_at).toLocaleString()}>{timeAgo(a.created_at)}</div>
          </div>
        </li>
      ))}
      {acts.total > acts.items.length && <li className="pt-3 text-xs text-muted">Showing latest {acts.items.length} of {acts.total} events.</li>}
    </ol>
  );
}

function Notes({ leadId, notes, names, canWrite, onChange }: { leadId: string; notes: Note[]; names: Record<string, string>; canWrite: boolean; onChange: () => void }) {
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true); setError(null);
    try { await crm.addNote(leadId, body.trim()); setBody(""); onChange(); } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }
  return (
    <div className="space-y-4">
      {canWrite && (
        <form onSubmit={add} className="card space-y-3 p-4">
          {error && <Alert>{error}</Alert>}
          <Textarea aria-label="New note" rows={3} placeholder="Write a note…" value={body} onChange={(e) => setBody(e.target.value)} maxLength={10000} />
          <div className="flex justify-end"><Button type="submit" loading={busy} disabled={!body.trim()} className="h-9 px-4 text-sm">Add note</Button></div>
        </form>
      )}
      {notes.length === 0 ? <div className="card p-8 text-center text-sm text-muted"><MessageSquare className="mx-auto mb-2 h-5 w-5" />No notes yet.</div> : notes.map((n) => (
        <article key={n.id} className="card p-5">
          <div className="mb-2 flex justify-between text-xs text-muted"><span className="font-medium text-neutral-900">{n.author_user_id ? names[n.author_user_id] ?? "Someone" : "System"}</span><span>{timeAgo(n.created_at)}</span></div>
          <p className="whitespace-pre-wrap text-sm text-neutral-800">{n.body}</p>
        </article>
      ))}
    </div>
  );
}

function Tasks({ leadId, tasks, members, names, canWrite, onChange }: {
  leadId: string; tasks: Task[]; members: Member[]; names: Record<string, string>; canWrite: boolean; onChange: () => void;
}) {
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [assignee, setAssignee] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function add(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await crm.addTask(leadId, { title: title.trim(), due_at: due ? new Date(due).toISOString() : null, assignee_user_id: assignee || null });
      setTitle(""); setDue(""); setAssignee(""); onChange();
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }
  async function toggle(t: Task) {
    setError(null);
    try { await crm.updateTask(t.id, { completed: !t.completed_at }); onChange(); } catch (err) { setError((err as Error).message); }
  }
  const sorted = [...tasks].sort((a, b) => Number(!!a.completed_at) - Number(!!b.completed_at));
  return (
    <div className="space-y-4">
      {error && <Alert>{error}</Alert>}
      {canWrite && (
        <form onSubmit={add} className="card flex flex-wrap items-end gap-3 p-4">
          <div className="min-w-[200px] flex-1"><label className="label" htmlFor="t-title">New task</label><Input id="t-title" className="h-10" required maxLength={300} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Follow up call…" /></div>
          <div><label className="label" htmlFor="t-due">Due</label><Input id="t-due" className="h-10" type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} /></div>
          <div><label className="label" htmlFor="t-as">Assignee</label>
            <Select id="t-as" value={assignee} onChange={(e) => setAssignee(e.target.value)}><option value="">Unassigned</option>{members.map((m) => <option key={m.user_id} value={m.user_id}>{m.full_name}</option>)}</Select></div>
          <Button type="submit" loading={busy} disabled={!title.trim()} className="h-10 px-4 text-sm"><Plus className="h-4 w-4" />Add</Button>
        </form>
      )}
      {sorted.length === 0 ? <div className="card p-8 text-center text-sm text-muted">No tasks for this lead.</div> : (
        <ul className="card divide-y divide-line">
          {sorted.map((t) => {
            const overdue = !t.completed_at && t.due_at && new Date(t.due_at) < new Date();
            return (
              <li key={t.id} className="flex items-center gap-3 px-5 py-3.5">
                <button disabled={!canWrite} onClick={() => toggle(t)} aria-label={t.completed_at ? "Mark incomplete" : "Mark complete"} className="text-muted hover:text-accent disabled:cursor-not-allowed">
                  {t.completed_at ? <CheckCircle2 className="h-5 w-5 text-success" /> : <Circle className="h-5 w-5" />}
                </button>
                <div className="min-w-0 flex-1">
                  <div className={`text-sm ${t.completed_at ? "text-muted line-through" : ""}`}>{t.title}</div>
                  <div className="flex flex-wrap gap-3 text-xs text-muted">
                    {t.due_at && <span className={`inline-flex items-center gap-1 ${overdue ? "text-danger" : ""}`}><CalendarClock className="h-3 w-3" />{fmtDateTime(t.due_at)}{overdue && " · overdue"}</span>}
                    {t.assignee_user_id && <span>{names[t.assignee_user_id] ?? "Unknown"}</span>}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function StatusDialog({ open, onClose, lead, isAdmin, onDone }: { open: boolean; onClose: () => void; lead: Lead; isAdmin: boolean; onDone: (l: Lead) => void }) {
  const allowed = allowedNext(lead.status);
  const [override, setOverride] = useState(false);
  const [target, setTarget] = useState<LeadStatus | "">("");
  const [consent, setConsent] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (open) { setOverride(false); setTarget(""); setConsent(lead.consent_reference ?? ""); setReason(""); setError(null); } }, [open, lead.consent_reference]);
  const options = override ? STATUSES.filter((s) => s !== lead.status) : allowed;
  const needsConsent = !!target && CONSENT_REQUIRED.includes(target as LeadStatus);
  const isOverride = !!target && !allowed.includes(target as LeadStatus);

  async function submit() {
    if (!target) return;
    setBusy(true); setError(null);
    try {
      onDone(await crm.changeStatus(lead.id, {
        status: target, consent_reference: needsConsent ? consent.trim() : undefined,
        reason: reason.trim() || undefined, admin_override: isOverride,
      }));
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <Dialog open={open} onClose={onClose} title="Change status" description={`Currently ${statusLabel(lead.status)}. Only lifecycle-valid moves are offered.`}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button onClick={submit} loading={busy} disabled={!target || (needsConsent && !consent.trim()) || (isOverride && !reason.trim())}>Update status</Button></>}>
      <div className="space-y-4">
        {error && <Alert>{error}</Alert>}
        {options.length === 0 && !override ? (
          <p className="text-sm text-muted">{statusLabel(lead.status)} is a final state — no further transitions are allowed{isAdmin ? " without an admin override" : ""}.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {options.map((s) => (
              <button key={s} onClick={() => setTarget(s)}
                className={`rounded-full px-3 py-1.5 text-sm ring-1 ring-inset transition ${target === s ? "bg-accent text-white ring-accent" : "bg-white ring-line hover:bg-raised"}`}>
                {statusLabel(s)}
              </button>
            ))}
          </div>
        )}
        {needsConsent && (
          <div><label className="label" htmlFor="consent">Consent reference <span className="text-danger">*</span></label>
            <Input id="consent" value={consent} maxLength={255} onChange={(e) => setConsent(e.target.value)} placeholder="e.g. signed form #1234, call recording ID" />
            <p className="mt-1 text-xs text-muted">Required: document where the lead&apos;s recorded consent to outreach is stored.</p></div>
        )}
        {isAdmin && (
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={override} onChange={(e) => { setOverride(e.target.checked); setTarget(""); }} className="h-4 w-4 accent-[#0071e3]" />
            Admin override (bypass lifecycle rules)</label>
        )}
        {(isOverride || override) && (
          <div><label className="label" htmlFor="reason">Reason {isOverride && <span className="text-danger">*</span>}</label>
            <Textarea id="reason" rows={2} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why is this override necessary? (audited)" /></div>
        )}
      </div>
    </Dialog>
  );
}

function EditDialog({ open, onClose, lead, members, onDone }: { open: boolean; onClose: () => void; lead: Lead; members: Member[]; onDone: (l: Lead) => void }) {
  const fields = ["business_name", "industry", "email", "phone", "website", "city", "country", "score", "owner_user_id"] as const;
  type F = Record<(typeof fields)[number], string>;
  const init = (): F => Object.fromEntries(fields.map((k) => [k, lead[k] == null ? "" : String(lead[k])])) as F;
  const [f, setF] = useState<F>(init);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dupId, setDupId] = useState<string | null>(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (open) { setF(init()); setError(null); setDupId(null); } }, [open, lead]);
  const set = (k: keyof F) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF((x) => ({ ...x, [k]: e.target.value }));

  async function save() {
    if (!f.business_name.trim()) { setError("Business name is required"); return; }
    if (f.country && !/^[A-Za-z]{2}$/.test(f.country)) { setError("Country must be a 2-letter code"); return; }
    const score = f.score === "" ? null : Number(f.score);
    if (score !== null && (!Number.isInteger(score) || score < 0 || score > 100)) { setError("Score must be 0–100"); return; }
    const body: LeadInput = {};
    for (const k of fields) {
      const before = lead[k] == null ? "" : String(lead[k]);
      if (f[k] === before) continue;
      (body as Record<string, unknown>)[k] = k === "score" ? score : f[k].trim() === "" ? null : f[k].trim();
    }
    if (!Object.keys(body).length) { onClose(); return; }
    setBusy(true); setError(null); setDupId(null);
    try { onDone(await crm.updateLead(lead.id, body)); } catch (e) { setDupId(duplicateLeadId(e)); setError((e as Error).message); } finally { setBusy(false); }
  }
  const L = (k: keyof F, label: string, extra?: React.InputHTMLAttributes<HTMLInputElement>) => (
    <div><label className="label" htmlFor={`e-${k}`}>{label}</label><Input id={`e-${k}`} value={f[k]} onChange={set(k)} {...extra} /></div>
  );
  return (
    <Dialog open={open} onClose={onClose} title="Edit lead" wide
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={save} loading={busy}>Save changes</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        {error && <div className="sm:col-span-2"><Alert>{error}{dupId && <> — <Link href={`/leads/${dupId}`} className="font-medium underline">open existing lead</Link></>}</Alert></div>}
        <div className="sm:col-span-2">{L("business_name", "Business name", { maxLength: 300 })}</div>
        {L("industry", "Industry")}
        <div><label className="label" htmlFor="e-owner">Owner</label>
          <Select id="e-owner" className="h-12 w-full" value={f.owner_user_id} onChange={set("owner_user_id")}>
            <option value="">Unassigned</option>{members.map((m) => <option key={m.user_id} value={m.user_id}>{m.full_name}</option>)}
          </Select></div>
        {L("email", "Email", { type: "email" })}
        {L("phone", "Phone")}
        <div className="sm:col-span-2">{L("website", "Website")}</div>
        {L("city", "City")}
        <div className="grid grid-cols-2 gap-3">{L("country", "Country", { maxLength: 2 })}{L("score", "Score", { type: "number", min: 0, max: 100 })}</div>
      </div>
    </Dialog>
  );
}

function DeleteLead({ open, onClose, lead, onDone }: { open: boolean; onClose: () => void; lead: Lead; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <ConfirmDialog open={open} onClose={onClose} danger loading={busy} confirmLabel="Delete lead" title="Delete this lead?"
      body={<>{error && <div className="mb-3"><Alert>{error}</Alert></div>}<strong>{lead.business_name}</strong> will be removed from your pipeline. This action is audited.</>}
      onConfirm={async () => {
        setBusy(true); setError(null);
        try { await crm.deleteLead(lead.id); onDone(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
      }} />
  );
}
