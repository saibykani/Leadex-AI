"use client";
import { useCallback, useEffect, useState } from "react";
import { Building2, OctagonX, ScrollText, ShieldAlert, Users } from "lucide-react";
import { useSession } from "@/lib/session-context";
import { CHANNELS, adminApi, type AdminAudit, type AdminOrg, type AdminUser, type KillSwitch, type Usage } from "@/lib/compliance";
import { Alert, Badge, Button, EmptyState, Input, PageHeader, Select, Skeleton, StatCard, Table, Tabs, useToast } from "@/components/ui";

type Tab = "orgs" | "users" | "audit" | "kill";
const fmt = (d: string | null) => (d ? new Date(d).toLocaleString() : "—");

export default function AdminPage() {
  const { me } = useSession();
  const [tab, setTab] = useState<Tab>("orgs");
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadUsage = useCallback(() => adminApi.usage().then(setUsage).catch((e) => setError((e as Error).message)), []);
  useEffect(() => { if (me.user.is_superadmin) void loadUsage(); }, [me.user.is_superadmin, loadUsage]);

  if (!me.user.is_superadmin) {
    return <EmptyState icon={<ShieldAlert className="h-5 w-5" />} title="Super admin only" body="This console is restricted to platform super administrators." />;
  }
  return (
    <div className="space-y-6">
      <PageHeader title="Platform admin" description="Cross-tenant operations. Every action here is audit-logged." />
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-4 sm:grid-cols-4">
        <StatCard label="Organizations" value={usage?.organizations} icon={<Building2 className="h-4 w-4" />} />
        <StatCard label="Active orgs" value={usage?.active_organizations} tone="success" icon={<Building2 className="h-4 w-4" />} />
        <StatCard label="Users" value={usage?.users} tone="violet" icon={<Users className="h-4 w-4" />} />
        <StatCard label="Leads" value={usage?.leads} tone="neutral" icon={<ScrollText className="h-4 w-4" />} />
      </div>
      <Tabs tabs={[{ id: "orgs", label: "Organizations" }, { id: "users", label: "Users" }, { id: "audit", label: "Audit log" }, { id: "kill", label: "Global kill switches" }]}
        value={tab} onChange={setTab} />
      {tab === "orgs" && <Orgs usage={usage} onChange={loadUsage} />}
      {tab === "users" && <UsersTab />}
      {tab === "audit" && <Audit />}
      {tab === "kill" && <GlobalKill />}
    </div>
  );
}

function Orgs({ usage, onChange }: { usage: Usage | null; onChange: () => void }) {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [data, setData] = useState<AdminOrg[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback((s: string) => adminApi.orgs(s).then((p) => setData(p.items)).catch((e) => setError((e as Error).message)), []);
  useEffect(() => { void load(""); }, [load]);
  const counts = new Map(usage?.per_organization.map((u) => [u.organization_id, u]) ?? []);
  async function toggle(o: AdminOrg) {
    setError(null);
    try {
      if (o.status === "suspended") await adminApi.reactivate(o.id);
      else {
        const reason = window.prompt(`Reason for suspending ${o.name}?`);
        if (!reason) return;
        await adminApi.suspend(o.id, reason);
      }
      toast("Organization updated", "success"); await load(q); onChange();
    } catch (e) { setError((e as Error).message); }
  }
  return (
    <div className="space-y-3">
      <form onSubmit={(e) => { e.preventDefault(); setData(null); void load(q); }} className="flex max-w-md gap-2">
        <Input className="h-10" placeholder="Search organizations" value={q} onChange={(e) => setQ(e.target.value)} />
        <Button type="submit" variant="outline" className="h-10">Search</Button>
      </form>
      {error && <Alert>{error}</Alert>}
      {!data ? <Skeleton className="h-40 w-full" /> : data.length === 0 ? <EmptyState icon={<Building2 className="h-5 w-5" />} title="No organizations" body="Nothing matches this search." /> : (
        <Table head={["Name", "Country", "Members", "Leads", "Status", "Created", ""]}>
          {data.map((o) => (
            <tr key={o.id}>
              <td className="px-5 py-3 font-medium">{o.name}{o.is_platform_owner && <Badge tone="violet" className="ml-2">platform</Badge>}</td>
              <td className="px-5 py-3 text-muted">{o.country_code ?? "—"}</td>
              <td className="px-5 py-3 tabular-nums">{counts.get(o.id)?.members ?? "—"}</td>
              <td className="px-5 py-3 tabular-nums">{counts.get(o.id)?.leads ?? "—"}</td>
              <td className="px-5 py-3"><Badge tone={o.status === "active" ? "success" : "danger"}>{o.status}</Badge></td>
              <td className="px-5 py-3 text-muted">{new Date(o.created_at).toLocaleDateString()}</td>
              <td className="px-5 py-3 text-right">{!o.is_platform_owner && (
                <Button variant="ghost" className="h-8 px-3 text-sm" onClick={() => toggle(o)}>{o.status === "suspended" ? "Reactivate" : "Suspend"}</Button>)}</td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}

function UsersTab() {
  const [q, setQ] = useState("");
  const [data, setData] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback((s: string) => adminApi.users(s).then((p) => setData(p.items)).catch((e) => setError((e as Error).message)), []);
  useEffect(() => { void load(""); }, [load]);
  return (
    <div className="space-y-3">
      <form onSubmit={(e) => { e.preventDefault(); setData(null); void load(q); }} className="flex max-w-md gap-2">
        <Input className="h-10" placeholder="Search users" value={q} onChange={(e) => setQ(e.target.value)} />
        <Button type="submit" variant="outline" className="h-10">Search</Button>
      </form>
      {error && <Alert>{error}</Alert>}
      {!data ? <Skeleton className="h-40 w-full" /> : data.length === 0 ? <EmptyState icon={<Users className="h-5 w-5" />} title="No users" body="Nothing matches this search." /> : (
        <Table head={["Name", "Email", "MFA", "Flags", "Last login"]}>
          {data.map((u) => (
            <tr key={u.id}>
              <td className="px-5 py-3 font-medium">{u.full_name}</td>
              <td className="px-5 py-3 text-muted">{u.email}</td>
              <td className="px-5 py-3">{u.mfa_enabled ? <Badge tone="success">On</Badge> : <Badge>Off</Badge>}</td>
              <td className="space-x-1 px-5 py-3">{u.is_superadmin && <Badge tone="violet">super admin</Badge>}{!u.is_active && <Badge tone="danger">inactive</Badge>}</td>
              <td className="px-5 py-3 text-muted">{fmt(u.last_login_at)}</td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}

function Audit() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ items: AdminAudit[]; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setData(null); adminApi.audit(page).then(setData).catch((e) => setError((e as Error).message)); }, [page]);
  const pages = data ? Math.max(1, Math.ceil(data.total / 50)) : 1;
  return (
    <div className="space-y-3">
      {error && <Alert>{error}</Alert>}
      {!data ? <Skeleton className="h-60 w-full" /> : data.items.length === 0 ? <EmptyState icon={<ScrollText className="h-5 w-5" />} title="No audit events" body="Events appear as users act across the platform." /> : (
        <>
          <Table head={["When", "Action", "Organization", "Entity", "Actor", "IP"]}>
            {data.items.map((a) => (
              <tr key={a.id}>
                <td className="whitespace-nowrap px-5 py-3 text-muted">{fmt(a.created_at)}</td>
                <td className="px-5 py-3 font-mono text-xs">{a.action}</td>
                <td className="px-5 py-3 font-mono text-xs text-muted">{a.organization_id?.slice(0, 8) ?? "platform"}</td>
                <td className="px-5 py-3 text-muted">{a.entity_type ?? "—"}</td>
                <td className="px-5 py-3 font-mono text-xs text-muted">{a.actor_user_id?.slice(0, 8) ?? "—"}</td>
                <td className="px-5 py-3 text-muted">{a.ip_address ?? "—"}</td>
              </tr>
            ))}
          </Table>
          <div className="flex items-center justify-end gap-2 text-sm text-muted">
            <Button variant="outline" className="h-9" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
            <span>Page {page} of {pages}</span>
            <Button variant="outline" className="h-9" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
          </div>
        </>
      )}
    </div>
  );
}

function GlobalKill() {
  const toast = useToast();
  const [data, setData] = useState<KillSwitch[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [channel, setChannel] = useState("all");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => adminApi.killSwitches().then(setData).catch((e) => setError((e as Error).message)), []);
  useEffect(() => { void load(); }, [load]);
  async function activate(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try { await adminApi.createKillSwitch(channel, reason); setReason(""); toast("Global kill switch active", "success"); await load(); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }
  async function release(id: string) {
    try { await adminApi.deactivateKillSwitch(id); await load(); } catch (err) { setError((err as Error).message); }
  }
  return (
    <div className="space-y-4">
      {error && <Alert>{error}</Alert>}
      <form onSubmit={activate} className="card grid gap-4 p-6 sm:grid-cols-[160px_1fr_auto] sm:items-end">
        <div><label className="label" htmlFor="gk-ch">Channel</label>
          <Select id="gk-ch" className="w-full" value={channel} onChange={(e) => setChannel(e.target.value)}>{["all", ...CHANNELS].map((c) => <option key={c}>{c}</option>)}</Select></div>
        <div><label className="label" htmlFor="gk-r">Reason</label><Input id="gk-r" className="h-10" required value={reason} onChange={(e) => setReason(e.target.value)} /></div>
        <Button type="submit" loading={busy} disabled={!reason} className="h-10 bg-danger hover:bg-danger/90"><OctagonX className="h-4 w-4" />Stop all tenants</Button>
      </form>
      {!data ? <Skeleton className="h-32 w-full" /> : data.length === 0 ? <EmptyState icon={<OctagonX className="h-5 w-5" />} title="No global kill switches" body="A global switch blocks the channel for every organization." /> : (
        <Table head={["Channel", "Reason", "Since", "State", ""]}>
          {data.map((k) => (
            <tr key={k.id}>
              <td className="px-5 py-3">{k.channel}</td>
              <td className="px-5 py-3 text-muted">{k.reason}</td>
              <td className="px-5 py-3 text-muted">{fmt(k.created_at)}</td>
              <td className="px-5 py-3">{k.active ? <Badge tone="danger">Active</Badge> : <Badge>Released</Badge>}</td>
              <td className="px-5 py-3 text-right">{k.active && <Button variant="ghost" className="h-8 px-3 text-sm" onClick={() => release(k.id)}>Release</Button>}</td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  );
}
