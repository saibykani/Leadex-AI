"use client";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { ArrowRight, Bot, Building2, FlaskConical, Gift, Globe2, Megaphone, RefreshCcw, ShieldCheck, Trash2, Users, Workflow } from "lucide-react";
import { useRouter } from "next/navigation";
import { growth, type DemoInfo } from "@/lib/growth";
import { useSession } from "@/lib/session-context";
import { Alert, AnimatedNumber, Badge, Button, ConfirmDialog, PageHeader, Skeleton, useToast } from "@/components/ui";

const COUNT_META: Record<string, { label: string; icon: typeof Users }> = {
  businesses: { label: "Businesses", icon: Building2 }, leads: { label: "Leads across stages", icon: Users },
  agents: { label: "AI agents", icon: Bot }, websites: { label: "Websites", icon: Globe2 }, campaigns: { label: "Campaigns", icon: Megaphone },
  referrals: { label: "Referrals", icon: Gift }, workflow_runs: { label: "Workflow runs", icon: Workflow },
};

export default function DemoPage() {
  const { reload, switchOrg, current } = useSession();
  const router = useRouter();
  const toast = useToast();
  const [info, setInfo] = useState<DemoInfo | null>(null);
  const [busy, setBusy] = useState<"create" | "reset" | "delete" | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { growth.demo().then(setInfo).catch((e) => setError(e.message)); }, []);

  const enter = async (d: DemoInfo) => {
    await reload();
    if (d.organization_id) switchOrg(d.organization_id);
    router.push("/dashboard");
  };
  const run = async (kind: "create" | "reset") => {
    setBusy(kind); setError(null);
    try {
      const d = kind === "create" ? await growth.createDemo() : await growth.resetDemo();
      setInfo(d);
      toast(kind === "create" ? "Demo workspace ready" : "Demo workspace reset", "success");
      await enter(d);
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };
  const remove = async () => {
    setBusy("delete");
    try {
      const wasCurrent = info?.organization_id === current.organization.id;
      await growth.deleteDemo();
      setInfo({ exists: false, organization_id: null, summary: null });
      setConfirm(false);
      toast("Demo workspace deleted", "success");
      await reload();
      if (wasCurrent) router.push("/dashboard");
    } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  };

  const inDemo = info?.exists && info.organization_id === current.organization.id;
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader eyebrow="Investor demo mode" title={<>Show the product <span className="text-gradient">with life in it</span></>}
        description="Spin up a separate workspace pre-filled with clearly-labelled fictional data — your real workspaces and analytics are never touched." />
      {error && <Alert>{error}</Alert>}

      <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="ring-gradient relative overflow-hidden rounded-3xl border border-line bg-surface p-6 shadow-card sm:p-8">
        <div aria-hidden className="lx-blob absolute -right-24 -top-24 h-72 w-72 rounded-full bg-[#f59e0b]/15 blur-3xl" />
        <div aria-hidden className="lx-blob lx-delay-2 absolute -bottom-24 left-10 h-64 w-64 rounded-full bg-[#5e5ce6]/15 blur-3xl" />
        <div className="relative flex flex-col gap-6 sm:flex-row sm:items-center">
          <div className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 text-white shadow-lg"><FlaskConical className="h-8 w-8" /></div>
          <div className="flex-1">
            {!info ? <Skeleton className="h-12 w-full" /> : info.exists ? (
              <>
                <div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-semibold">{info.name}</h2><Badge tone="warning" dot>Fictional data</Badge>{inDemo && <Badge tone="accent">You are here</Badge>}</div>
                <p className="mt-1 text-sm text-muted">Created {info.created_at ? new Date(info.created_at).toLocaleString() : ""}. Every page in it shows a “Demo workspace — fictional data” banner.</p>
              </>
            ) : (
              <>
                <h2 className="text-lg font-semibold">No demo workspace yet</h2>
                <p className="mt-1 text-sm text-muted">One click creates a new organization you own, seeded with invented businesses, leads with stated budgets, AI agent runs, websites, campaigns, referrals and workflow runs.</p>
              </>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            {info && !info.exists && <Button variant="gradient" size="lg" loading={busy === "create"} onClick={() => run("create")}><FlaskConical className="h-4 w-4" />Create demo workspace</Button>}
            {info?.exists && !inDemo && <Button variant="gradient" onClick={() => enter(info)}>Open demo<ArrowRight className="h-4 w-4" /></Button>}
            {info?.exists && <Button variant="outline" loading={busy === "reset"} onClick={() => run("reset")}><RefreshCcw className="h-4 w-4" />Reset</Button>}
            {info?.exists && <Button variant="ghost" className="text-danger hover:bg-danger/5 hover:text-danger" onClick={() => setConfirm(true)}><Trash2 className="h-4 w-4" />Delete</Button>}
          </div>
        </div>
        {info?.exists && info.summary?.counts && (
          <div className="relative mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Object.entries(info.summary.counts).map(([k, n], i) => {
              const m = COUNT_META[k] ?? { label: k, icon: Users };
              return (
                <motion.div key={k} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} className="rounded-2xl border border-line bg-surface/70 p-3 backdrop-blur">
                  <m.icon className="h-4 w-4 text-accent" />
                  <div className="mt-2 font-display text-2xl font-semibold"><AnimatedNumber value={n} /></div>
                  <div className="text-xs text-muted">{m.label}</div>
                </motion.div>
              );
            })}
          </div>
        )}
      </motion.section>

      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { icon: ShieldCheck, t: "Isolated", b: "A separate organization with its own row-level security. Nothing is mixed into real tenants." },
          { icon: FlaskConical, t: "Clearly labelled", b: "Banner on every page, example.com contacts, “(Demo)” providers, simulated flags on runs and outcomes." },
          { icon: RefreshCcw, t: "Disposable", b: "Reset to a fresh dataset before each meeting, or delete it in one click." },
        ].map((x, i) => (
          <motion.div key={x.t} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.06 }} className="card card-hover p-5">
            <x.icon className="h-5 w-5 text-accent" /><h3 className="mt-3 font-semibold">{x.t}</h3><p className="mt-1 text-sm text-muted">{x.b}</p>
          </motion.div>
        ))}
      </div>

      <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} onConfirm={remove} loading={busy === "delete"} danger confirmLabel="Delete demo"
        title="Delete demo workspace?" body="The demo organization and its fictional data will be removed from your account. Your real workspaces are unaffected." />
    </div>
  );
}
