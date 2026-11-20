"use client";
import { api } from "@/lib/api";
type Voice = { id: string; label: string; gender: string; tier: string; languages: string[] };
import clsx from "clsx";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import {
  agentsApi, lines, type Agent, type Evaluation, type Knowledge, type Language, type ModelConfig, type Tool, type Version,
} from "@/lib/agents";
import { useSession } from "@/lib/session-context";
import { Alert, Button, Input, LinkButton } from "@/components/ui";
import { StatusBadge, Textarea } from "./_ui";

const TABS = ["profile", "script", "knowledge", "tools", "compliance"] as const;
type Tab = (typeof TABS)[number];

type Form = {
  name: string; purpose: string; industry: string; personality: string; voice: string; language: string; speaking_rate: number;
  greeting: string; business_info: string; questions: string; flow: string; objections: string; tools: string[];
  escalation_policy: string; max_call_seconds: number; compliance_disclosure: string; model_config_id: string;
};

function toForm(a?: Agent): Form {
  return {
    name: a?.name ?? "", purpose: a?.purpose ?? "", industry: a?.industry ?? "", personality: a?.personality ?? "",
    voice: a?.voice ?? "", language: a?.language ?? "en", speaking_rate: a?.speaking_rate ?? 1, greeting: a?.greeting ?? "",
    business_info: a?.business_info ?? "", questions: (a?.qualification_questions ?? []).join("\n"),
    flow: (a?.conversation_flow ?? []).join("\n"),
    objections: (a?.objection_handling ?? []).map((o) => `${o.objection} => ${o.response}`).join("\n"),
    tools: a?.tools ?? [], escalation_policy: a?.escalation_policy ?? "", max_call_seconds: a?.max_call_seconds ?? 300,
    compliance_disclosure: a?.compliance_disclosure ?? "", model_config_id: a?.model_config_id ?? "",
  };
}

function toBody(f: Form) {
  return {
    name: f.name, purpose: f.purpose || null, industry: f.industry || null, personality: f.personality || null,
    voice: f.voice || null, language: f.language, speaking_rate: Number(f.speaking_rate), greeting: f.greeting || null,
    business_info: f.business_info || null, qualification_questions: lines(f.questions), conversation_flow: lines(f.flow),
    objection_handling: lines(f.objections).map((l) => { const [o, r] = l.split("=>"); return { objection: o.trim(), response: (r ?? "").trim() }; }),
    tools: f.tools, escalation_policy: f.escalation_policy || null, max_call_seconds: Number(f.max_call_seconds),
    compliance_disclosure: f.compliance_disclosure, model_config_id: f.model_config_id || null,
  };
}

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return <div><label className="label" htmlFor={id}>{label}</label>{children}</div>;
}

export function AgentBuilder({ agent: initial }: { agent?: Agent }) {
  const router = useRouter();
  const { can } = useSession();
  const editable = can("agents:write");
  const [agent, setAgent] = useState<Agent | undefined>(initial);
  const [form, setForm] = useState<Form>(toForm(initial));
  const [tab, setTab] = useState<Tab>("profile");
  const [tools, setTools] = useState<Tool[]>([]);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [knowledge, setKnowledge] = useState<Knowledge[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [evals, setEvals] = useState<Evaluation[]>([]);
  const [doc, setDoc] = useState({ title: "", content: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));

  useEffect(() => {
    agentsApi.tools().then(setTools).catch(() => {});
    agentsApi.languages().then(setLanguages).catch(() => {});
    api<{ items: Voice[] }>("/voices", {}, true).then((r) => setVoices(r.items)).catch(() => {});
    agentsApi.modelConfigs().then(setModels).catch(() => {});
  }, []);
  const loadExtra = useCallback(async (id: string) => {
    const [k, v, e] = await Promise.all([agentsApi.knowledge(id), agentsApi.versions(id), agentsApi.evaluations(id)]);
    setKnowledge(k); setVersions(v); setEvals(e);
  }, []);
  useEffect(() => { if (agent) void loadExtra(agent.id).catch((e) => setError(e.message)); }, [agent, loadExtra]);

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label); setError(null); setNotice(null);
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  }

  const save = () => run("save", async () => {
    if (agent) {
      const a = await agentsApi.update(agent.id, toBody(form));
      setAgent(a); setNotice(a.status === "draft" && agent.status === "published" ? "Saved. Changes require re-publishing." : "Saved.");
    } else {
      const a = await agentsApi.create(toBody(form));
      router.replace(`/agents/${a.id}`);
    }
  });
  const publish = () => run("publish", async () => {
    if (!agent) return;
    const v = await agentsApi.publish(agent.id);
    setAgent(await agentsApi.get(agent.id)); setNotice(`Published version ${v.version}.`); await loadExtra(agent.id);
  });
  const toggleKill = () => run("kill", async () => {
    if (!agent) return;
    setAgent(agent.status === "killed" ? await agentsApi.reactivate(agent.id) : await agentsApi.kill(agent.id));
  });
  const addDoc = () => run("doc", async () => {
    if (!agent) return;
    const k = await agentsApi.addKnowledge(agent.id, doc.title, doc.content);
    setDoc({ title: "", content: "" });
    setNotice(`Indexed ${k.chunk_count} chunk(s) · ${k.embedding_status === "embedded" ? "vector search" : "keyword search only (embeddings unavailable)"}`);
    await loadExtra(agent.id);
  });
  const delDoc = (kid: string) => run("doc", async () => { if (agent) { await agentsApi.deleteKnowledge(agent.id, kid); await loadExtra(agent.id); } });

  const lang = languages.find((l) => l.code === form.language);
  const langPassed = evals.some((e) => e.kind === "language" && e.language === form.language && e.passed);

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href="/agents" className="text-sm text-accent">← Agents</Link>
          <h1 className="mt-1 flex items-center gap-3 text-xl font-semibold">{agent ? agent.name : "New agent"} {agent && <StatusBadge status={agent.status} />}</h1>
          {agent?.published_version && <p className="mt-1 text-sm text-muted">Live version v{agent.published_version}</p>}
        </div>
        {agent && (
          <div className="flex flex-wrap gap-2">
            <LinkButton href={`/agents/${agent.id}/test`} variant="outline">Test lab</LinkButton>
            {editable && <Button variant="outline" loading={busy === "kill"} onClick={toggleKill}>{agent.status === "killed" ? "Reactivate" : "Kill switch"}</Button>}
            {editable && agent.status !== "killed" && <Button loading={busy === "publish"} onClick={publish}>Publish</Button>}
          </div>
        )}
      </div>
      {error && <Alert>{error}</Alert>}
      {notice && <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800">{notice}</div>}

      <div className="flex gap-1 border-b border-line">
        {TABS.map((t) => (
          <button key={t} type="button" onClick={() => setTab(t)} disabled={t === "knowledge" && !agent}
            className={clsx("-mb-px border-b-2 px-4 py-2 text-sm capitalize disabled:opacity-40", tab === t ? "border-accent font-medium text-neutral-900" : "border-transparent text-muted hover:text-neutral-900")}>
            {t}
          </button>
        ))}
      </div>

      <fieldset disabled={!editable} className="card space-y-4 p-6">
        {tab === "profile" && (<>
          <Field label="Name" id="f-name"><Input id="f-name" required value={form.name} onChange={(e) => set("name", e.target.value)} /></Field>
          <Field label="Purpose" id="f-purpose"><Input id="f-purpose" value={form.purpose} onChange={(e) => set("purpose", e.target.value)} /></Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Industry" id="f-ind"><Input id="f-ind" value={form.industry} onChange={(e) => set("industry", e.target.value)} /></Field>
            <Field label="Phone voice" id="f-voice">
              <select id="f-voice" value={form.voice} onChange={(e) => set("voice", e.target.value)} className="h-12 w-full rounded-xl border border-line bg-white px-4 text-[15px]">
                <option value="">Default (female voice for the language)</option>
                {voices.filter((v) => v.languages.some((l) => l.startsWith(form.language + "-"))).map((v) => (
                  <option key={v.id} value={v.id}>{v.gender === "female" ? "♀" : "♂"} {v.label}{v.tier !== "standard" ? " · natural (may cost extra)" : ""}</option>
                ))}
              </select>
            </Field>
            <Field label="Language" id="f-lang">
              <select id="f-lang" value={form.language} onChange={(e) => set("language", e.target.value)} className="h-12 w-full rounded-xl border border-line bg-white px-4 text-[15px]">
                {languages.map((l) => <option key={l.code} value={l.code}>{l.name}{l.status !== "enabled" ? " (evaluation pending)" : ""}</option>)}
              </select>
            </Field>
            <Field label="Speaking rate" id="f-rate"><Input id="f-rate" type="number" min={0.5} max={2} step={0.1} value={form.speaking_rate} onChange={(e) => set("speaking_rate", Number(e.target.value))} /></Field>
            <Field label="Model configuration" id="f-model">
              <select id="f-model" value={form.model_config_id} onChange={(e) => set("model_config_id", e.target.value)} className="h-12 w-full rounded-xl border border-line bg-white px-4 text-[15px]">
                <option value="">Simulated (template responses, no AI model)</option>
                {models.map((m) => <option key={m.id} value={m.id}>{m.name} · {m.provider}/{m.model}</option>)}
              </select>
            </Field>
          </div>
          <Field label="Personality" id="f-pers"><Textarea id="f-pers" rows={2} value={form.personality} onChange={(e) => set("personality", e.target.value)} /></Field>
          <Field label="Business information" id="f-biz"><Textarea id="f-biz" rows={4} value={form.business_info} onChange={(e) => set("business_info", e.target.value)} /></Field>
        </>)}

        {tab === "script" && (<>
          <Field label="Greeting" id="f-greet"><Textarea id="f-greet" rows={2} value={form.greeting} onChange={(e) => set("greeting", e.target.value)} /></Field>
          <Field label="Qualification questions (one per line)" id="f-q"><Textarea id="f-q" rows={5} value={form.questions} onChange={(e) => set("questions", e.target.value)} /></Field>
          <Field label="Conversation flow steps (one per line)" id="f-flow"><Textarea id="f-flow" rows={5} value={form.flow} onChange={(e) => set("flow", e.target.value)} /></Field>
          <Field label="Objection handling (objection => response, one per line)" id="f-obj"><Textarea id="f-obj" rows={4} value={form.objections} onChange={(e) => set("objections", e.target.value)} /></Field>
        </>)}

        {tab === "knowledge" && agent && (<>
          <p className="text-sm text-muted">Documents are chunked and embedded with Ollama into Qdrant when available; otherwise they are searchable by keyword only. Answers cite their sources.</p>
          <Field label="Title" id="k-title"><Input id="k-title" value={doc.title} onChange={(e) => setDoc({ ...doc, title: e.target.value })} /></Field>
          <Field label="Content" id="k-content"><Textarea id="k-content" rows={6} value={doc.content} onChange={(e) => setDoc({ ...doc, content: e.target.value })} /></Field>
          <Button type="button" loading={busy === "doc"} disabled={!doc.title || !doc.content} onClick={addDoc}>Add document</Button>
          <ul className="divide-y divide-line">
            {knowledge.map((k) => (
              <li key={k.id} className="flex items-center justify-between py-3 text-sm">
                <span><span className="font-medium">{k.title}</span> <span className="text-muted">v{k.version} · {k.chunk_count} chunks · {k.embedding_status.replace(/_/g, " ")}</span></span>
                <button type="button" aria-label={`Delete ${k.title}`} onClick={() => delDoc(k.id)} className="text-muted hover:text-danger"><Trash2 className="h-4 w-4" /></button>
              </li>
            ))}
            {knowledge.length === 0 && <li className="py-3 text-sm text-muted">No documents yet.</li>}
          </ul>
        </>)}

        {tab === "tools" && (<>
          <p className="text-sm text-muted">The agent can only call tools on this allow-list, and only with the permissions of the user running it. Tools that contact people go through the compliance gate.</p>
          {tools.map((t) => (
            <label key={t.key} className="flex items-start gap-3 rounded-xl border border-line p-4">
              <input type="checkbox" className="mt-1" checked={form.tools.includes(t.key)}
                onChange={(e) => set("tools", e.target.checked ? [...form.tools, t.key] : form.tools.filter((x) => x !== t.key))} />
              <span className="text-sm"><span className="font-medium">{t.name}</span> <span className="font-mono text-xs text-muted">{t.key}</span>
                <span className="block text-muted">{t.description}</span>
                <span className="block text-xs text-muted">Requires {t.required_permission}{t.side_effect ? " · side effect" : ""}{t.contacts_person ? " · compliance gated" : ""}</span></span>
            </label>
          ))}
        </>)}

        {tab === "compliance" && (<>
          <Field label="Compliance disclosure (required, spoken first on every call)" id="f-disc">
            <Textarea id="f-disc" rows={3} required minLength={10} value={form.compliance_disclosure} onChange={(e) => set("compliance_disclosure", e.target.value)} />
          </Field>
          <Field label="Escalation policy" id="f-esc"><Textarea id="f-esc" rows={2} value={form.escalation_policy} onChange={(e) => set("escalation_policy", e.target.value)} /></Field>
          <Field label="Max call length (seconds)" id="f-max"><Input id="f-max" type="number" min={30} max={3600} value={form.max_call_seconds} onChange={(e) => set("max_call_seconds", Number(e.target.value))} /></Field>
          {lang && lang.status !== "enabled" && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              {lang.name} is <b>evaluation pending</b>. {langPassed ? "A passed evaluation exists for this agent, so live calls are allowed." : "Live calls are blocked until an Owner/Admin records a passed language evaluation for this agent."}
            </div>
          )}
        </>)}
      </fieldset>

      {editable && tab !== "knowledge" && (
        <div className="flex justify-end"><Button loading={busy === "save"} disabled={!form.name || form.compliance_disclosure.length < 10} onClick={save}>{agent ? "Save changes" : "Create agent"}</Button></div>
      )}

      {versions.length > 0 && (
        <section className="card p-5">
          <h2 className="mb-2 text-sm font-medium">Published versions</h2>
          <ul className="space-y-1 text-sm text-muted">
            {versions.map((v) => <li key={v.id}>v{v.version} · {new Date(v.created_at).toLocaleString()}</li>)}
          </ul>
        </section>
      )}
    </div>
  );
}
