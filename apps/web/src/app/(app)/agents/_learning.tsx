"use client";
import { useCallback, useEffect, useState } from "react";
import { Brain, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session-context";
import { Alert, Badge, Button, Input } from "@/components/ui";

type Variant = {
  id: string; name: string; opening: string; active: boolean; calls_scored: number; wins: number;
  success_rate: number | null; posterior_mean: number; prob_best: number | null;
};
type Stats = { variants: Variant[]; baseline: { calls_scored: number; wins: number }; labels: Record<string, number> };

const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);

/** Self-learning: opening variants chosen by Thompson sampling, scored from real call outcomes. */
export function LearningPanel({ agentId }: { agentId: string }) {
  const { can } = useSession();
  const [s, setS] = useState<Stats | null>(null);
  const [name, setName] = useState("");
  const [opening, setOpening] = useState("");
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<Stats>(`/agents/${agentId}/learning`, {}, true).then(setS).catch((e) => setError(e.message)), [agentId]);
  useEffect(() => { void load(); }, [load]);

  async function add(e: React.FormEvent) {
    e.preventDefault(); setError(null);
    try {
      await api(`/agents/${agentId}/variants`, { method: "POST", body: JSON.stringify({ name, opening }) }, true);
      setName(""); setOpening(""); await load();
    } catch (err) { setError((err as Error).message); }
  }
  async function toggle(v: Variant) {
    try { await api(`/agents/${agentId}/variants/${v.id}`, { method: "PATCH", body: JSON.stringify({ active: !v.active }) }, true); await load(); }
    catch (err) { setError((err as Error).message); }
  }

  const scored = (s?.variants ?? []).reduce((n, v) => n + v.calls_scored, 0) + (s?.baseline.calls_scored ?? 0);
  return (
    <section className="card max-w-4xl space-y-5 p-6">
      <div>
        <h2 className="flex items-center gap-2 text-[15px] font-semibold"><Brain className="h-4 w-4 text-accent" />Self-learning</h2>
        <p className="mt-1 text-sm text-muted">
          Add different ways to open the call. On every real call the agent picks one using Thompson sampling: openings that lead
          to interested customers are used more, new ones still get tried. Replies from successful calls are reused as examples.
          Rate calls Good/Bad on the call page to teach it directly. Only real calls count; simulated calls are never used for learning.
        </p>
      </div>
      {error && <Alert>{error}</Alert>}
      <div className="flex flex-wrap gap-2 text-xs">
        <Badge>{scored} scored call{scored === 1 ? "" : "s"}</Badge>
        {Object.entries(s?.labels ?? {}).map(([k, n]) => <Badge key={k}>{k.replace(/_/g, " ")}: {n}</Badge>)}
      </div>
      {s && s.variants.length === 0 && <p className="text-sm text-muted">No openings yet. The agent uses its greeting until you add some (two or more are needed to compare).</p>}
      <ul className="space-y-3">
        {s?.variants.map((v) => (
          <li key={v.id} className="rounded-xl border border-line p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{v.name}</span>
              {!v.active && <Badge>paused</Badge>}
              {v.active && v.prob_best != null && v.calls_scored > 0 && <Badge tone={v.prob_best > 0.8 ? "success" : "neutral"}>{pct(v.prob_best)} chance best</Badge>}
              <span className="ml-auto text-xs text-muted">{v.calls_scored ? `${v.wins}/${v.calls_scored} successful · ${pct(v.success_rate)}` : "not tried yet"}</span>
              {can("agents:write") && <button className="text-xs font-medium text-accent hover:underline" onClick={() => toggle(v)}>{v.active ? "Pause" : "Resume"}</button>}
            </div>
            <p className="mt-1.5 text-sm text-muted">“{v.opening}”</p>
            {v.calls_scored > 0 && <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-raised"><div className="h-full bg-accent" style={{ width: pct(v.posterior_mean) }} /></div>}
          </li>
        ))}
      </ul>
      {can("agents:write") && (
        <form onSubmit={add} className="grid gap-2 sm:grid-cols-[180px_1fr_auto]">
          <Input placeholder="Name (e.g. Friendly)" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
          <Input placeholder="Opening line after the AI disclosure, e.g. “Namaste! Do you have one minute to talk about your website?”" value={opening} onChange={(e) => setOpening(e.target.value)} maxLength={600} />
          <Button type="submit" disabled={!name.trim() || opening.trim().length < 5}><Plus className="h-4 w-4" />Add</Button>
        </form>
      )}
    </section>
  );
}
