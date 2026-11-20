"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Workflow as WorkflowIcon, Plus } from "lucide-react";
import { useSession } from "@/lib/session-context";
import { Alert, Button, EmptyState, Input } from "@/components/ui";
import { workflows, type Analytics, type Approval, type Workflow } from "@/lib/workflows";

export default function WorkflowsPage() {
  const { current, can } = useSession();
  const router = useRouter();
  const [items, setItems] = useState<Workflow[] | null>(null);
  const [stats, setStats] = useState<Analytics | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setError(null);
    workflows.list().then((p) => setItems(p.items)).catch((e) => setError(e.message));
    workflows.analytics().then(setStats).catch(() => {});
    workflows.approvals().then(setApprovals).catch(() => {});
  }, []);
  useEffect(load, [load, current.organization.id]);

  const create = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const wf = await workflows.create(name.trim(), {
        nodes: [{ id: "trigger", type: "trigger", config: { trigger_type: "manual" }, position: { x: 80, y: 120 } }], edges: [],
      });
      router.push(`/workflows/${wf.id}`);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const decide = async (id: string, ok: boolean) => {
    try { await workflows.decide(id, ok); load(); } catch (e) { setError((e as Error).message); }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Workflows</h1>
        <p className="mt-1 text-sm text-muted">Automate lead handling. Outreach steps always pass the compliance gate.</p>
      </div>
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Workflows" value={items?.length ?? "—"} />
        <Stat label="Runs" value={stats?.total ?? "—"} />
        <Stat label="Succeeded" value={stats?.by_status.succeeded ?? 0} />
        <Stat label="Success rate" value={stats?.success_rate == null ? "—" : `${Math.round(stats.success_rate * 100)}%`} />
      </div>
      {can("workflows:write") && (
        <div className="card flex flex-col gap-3 p-4 sm:flex-row">
          <Input placeholder="New workflow name" value={name} onChange={(e) => setName(e.target.value)} />
          <Button onClick={create} loading={busy}><Plus className="h-4 w-4" />Create</Button>
        </div>
      )}
      {approvals.length > 0 && (
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-medium">Pending approvals</h2>
          <ul className="divide-y divide-line">
            {approvals.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span>{a.message || "Approval required"} <span className="text-muted">· node {a.node_key}</span></span>
                {can("workflows:write") && (
                  <span className="flex gap-2">
                    <Button variant="outline" className="h-9 px-4" onClick={() => decide(a.id, false)}>Reject</Button>
                    <Button className="h-9 px-4" onClick={() => decide(a.id, true)}>Approve</Button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      {items && items.length === 0 && (
        <EmptyState icon={<WorkflowIcon className="h-5 w-5" />} title="No workflows yet" body="Create one to start building with the visual editor." />
      )}
      {items && items.length > 0 && (
        <div className="card divide-y divide-line">
          {items.map((w) => (
            <Link key={w.id} href={`/workflows/${w.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-raised">
              <div>
                <div className="text-sm font-medium">{w.name}</div>
                <div className="text-xs text-muted">Trigger: {w.trigger_type ?? "not published"} · updated {new Date(w.updated_at).toLocaleString()}</div>
              </div>
              <span className="rounded-full bg-raised px-3 py-1 text-xs capitalize">{w.status}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}
