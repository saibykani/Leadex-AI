"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Bot, Plus } from "lucide-react";
import { agentsApi, type Agent, type Provider, type Template } from "@/lib/agents";
import { useSession } from "@/lib/session-context";
import { Alert, Button, EmptyState, LinkButton } from "@/components/ui";
import { StatusBadge } from "./_ui";

export default function AgentsPage() {
  const router = useRouter();
  const { can } = useSession();
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    agentsApi.list().then((p) => setAgents(p.items)).catch((e) => setError(e.message));
    agentsApi.templates().then(setTemplates).catch(() => {});
    agentsApi.providers().then(setProviders).catch(() => {});
  }, []);

  async function applyTemplate(key: string) {
    setBusy(key); setError(null);
    try { const a = await agentsApi.fromTemplate(key); router.push(`/agents/${a.id}`); }
    catch (e) { setError((e as Error).message); setBusy(null); }
  }

  return (
    <div className="max-w-5xl space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Voice agents</h1>
          <p className="mt-1 text-sm text-muted">Build, test and publish AI agents. Every call passes the compliance gate.</p>
        </div>
        <div className="flex gap-2">
          <LinkButton href="/calls" variant="outline">Call history</LinkButton>
          {can("agents:write") && <LinkButton href="/agents/new"><Plus className="h-4 w-4" />New agent</LinkButton>}
        </div>
      </div>
      {error && <Alert>{error}</Alert>}

      {providers.length > 0 && (
        <div className="flex flex-wrap gap-2 text-xs">
          {providers.map((p) => (
            <span key={p.provider} className="rounded-full border border-line bg-surface px-3 py-1" title={typeof p.detail === "string" ? p.detail : undefined}>
              <span className="font-medium">{p.provider}</span>{" "}
              <span className={p.status === "available" ? "text-green-700" : "text-muted"}>{p.status.replace(/_/g, " ")}</span>
              {p.simulated && <span className="ml-1 text-amber-700">(simulated)</span>}
            </span>
          ))}
        </div>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted">Your agents</h2>
        {agents === null ? <p className="text-sm text-muted">Loading…</p> : agents.length === 0 ? (
          <EmptyState icon={<Bot className="h-5 w-5" />} title="No agents yet" body="Start from a template below or create one from scratch." />
        ) : (
          <div className="card divide-y divide-line">
            {agents.map((a) => (
              <Link key={a.id} href={`/agents/${a.id}`} className="flex items-center gap-4 px-5 py-4 hover:bg-raised">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{a.name}</p>
                  <p className="truncate text-sm text-muted">{a.purpose ?? "No purpose set"} · {a.language.toUpperCase()}{a.published_version ? ` · v${a.published_version}` : ""}</p>
                </div>
                <StatusBadge status={a.status} />
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted">Templates</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((t) => (
            <div key={t.key} className="card flex flex-col p-5">
              <p className="font-medium">{t.name}</p>
              <p className="mt-1 flex-1 text-sm text-muted">{t.purpose}</p>
              <p className="mt-3 text-xs text-muted">Tools: {(t.tools ?? []).join(", ") || "none"}</p>
              {can("agents:write") && (
                <Button variant="outline" className="mt-4 h-9 text-sm" loading={busy === t.key} onClick={() => applyTemplate(t.key)}>Use template</Button>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
