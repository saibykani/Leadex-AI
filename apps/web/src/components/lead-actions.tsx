"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Bot, Globe2, ShieldCheck } from "lucide-react";
import { ApiError, isBillingError } from "@/lib/api";
import { agentsApi, callsApi, reasonLabel, type Agent, type Call } from "@/lib/agents";
import { BASES, CHANNELS, compliance } from "@/lib/compliance";
import { websites, type ProjectDetail, type Template } from "@/lib/websites";
import { Alert, Button, Dialog, Input, Select, useToast } from "@/components/ui";

const human = (s: string) => s.replace(/_/g, " ");

/** Billing (402) errors render with a link to /billing; everything else as plain text. */
function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <Alert>
      {msg}
      {isBillingError(error) && <> · <Link href="/billing" className="font-medium underline">Upgrade or review billing</Link></>}
    </Alert>
  );
}

export function LeadActions({ leadId, onChange }: { leadId: string; onChange: () => void }) {
  const [open, setOpen] = useState<"call" | "website" | "consent" | null>(null);
  const close = () => setOpen(null);
  return (
    <>
      <Button variant="outline" onClick={() => setOpen("call")}><Bot className="h-4 w-4" />Call with AI agent</Button>
      <Button variant="outline" onClick={() => setOpen("website")}><Globe2 className="h-4 w-4" />Generate website</Button>
      <Button variant="outline" onClick={() => setOpen("consent")}><ShieldCheck className="h-4 w-4" />Add consent</Button>
      {open === "call" && <CallDialog leadId={leadId} onClose={close} onDone={onChange} />}
      {open === "website" && <WebsiteDialog leadId={leadId} onClose={close} />}
      {open === "consent" && <ConsentDialog leadId={leadId} onClose={close} onDone={onChange} />}
    </>
  );
}

function CallDialog({ leadId, onClose, onDone }: { leadId: string; onClose: () => void; onDone: () => void }) {
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [agentId, setAgentId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [call, setCall] = useState<Call | null>(null);
  const [blocked, setBlocked] = useState<{ reasons: string[]; callId?: string } | null>(null);
  useEffect(() => {
    agentsApi.list().then((p) => {
      const live = p.items.filter((a) => a.status === "published");
      setAgents(live);
      if (live[0]) setAgentId(live[0].id);
    }).catch(setError);
  }, []);
  async function place() {
    setBusy(true); setError(null); setBlocked(null); setCall(null);
    try {
      setCall(await callsApi.create(leadId, agentId));
      onDone();
    } catch (e) {
      if (e instanceof ApiError && e.code === "call_blocked") {
        const d = (e.details ?? {}) as { reasons?: string[]; call_id?: string };
        setBlocked({ reasons: d.reasons ?? [], callId: d.call_id });
      } else setError(e);
    } finally { setBusy(false); }
  }
  return (
    <Dialog open onClose={onClose} title="Call with AI agent"
      description="Every call passes the compliance gate. Outside production calls are simulated and nobody is contacted."
      footer={<>
        <Button variant="ghost" onClick={onClose}>Close</Button>
        <Button onClick={place} loading={busy} disabled={!agentId || busy}>Place call</Button>
      </>}>
      <div className="space-y-3">
        <ErrorBox error={error} />
        {agents === null ? <p className="text-sm text-muted">Loading agents…</p> : agents.length === 0 ? (
          <p className="text-sm text-muted">No published agents. <Link href="/agents" className="text-accent hover:underline">Publish an agent</Link> first.</p>
        ) : (
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-muted">Agent</span>
            <Select value={agentId} onChange={(e) => setAgentId(e.target.value)} className="w-full">
              {agents.map((a) => <option key={a.id} value={a.id}>{a.name} (v{a.published_version}, {a.language})</option>)}
            </Select>
          </label>
        )}
        {blocked && (
          <div role="alert" className="rounded-xl border border-danger/30 bg-danger/5 p-3 text-sm">
            <div className="font-medium text-danger">Call blocked by compliance checks</div>
            <ul className="mt-1 list-disc pl-5 text-neutral-800">
              {blocked.reasons.map((r) => <li key={r}>{reasonLabel(r)}</li>)}
            </ul>
            {blocked.callId && <Link href={`/calls/${blocked.callId}`} className="mt-2 inline-block text-accent hover:underline">View call record</Link>}
          </div>
        )}
        {call && (
          <div className="rounded-xl bg-success/5 p-3 text-sm">
            <div className="font-medium text-success">
              {call.simulated ? "Simulated call completed (no one was contacted)" : `Call ${human(call.status)}`}
            </div>
            <div className="mt-0.5 text-xs text-muted">Status: {human(call.status)} · Provider: {call.provider}</div>
            <Link href={`/calls/${call.id}`} className="mt-2 inline-block text-accent hover:underline">Open call details</Link>
          </div>
        )}
      </div>
    </Dialog>
  );
}

function WebsiteDialog({ leadId, onClose }: { leadId: string; onClose: () => void }) {
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [project, setProject] = useState<ProjectDetail | null>(null);
  useEffect(() => {
    websites.templates().then((t) => { setTemplates(t); if (t[0]) setKey(t[0].key); }).catch(setError);
  }, []);
  async function generate() {
    setBusy(true); setError(null);
    try { setProject(await websites.generate({ template_key: key, lead_id: leadId })); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  return (
    <Dialog open onClose={onClose} title="Generate website" description="Creates a draft website from this lead's details."
      footer={<>
        <Button variant="ghost" onClick={onClose}>Close</Button>
        {!project && <Button onClick={generate} loading={busy} disabled={!key || busy}>Generate</Button>}
      </>}>
      <div className="space-y-3">
        <ErrorBox error={error} />
        {templates && (
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-muted">Template</span>
            <Select value={key} onChange={(e) => setKey(e.target.value)} className="w-full" disabled={!!project}>
              {templates.map((t) => <option key={t.key} value={t.key}>{t.name} · {t.industry}</option>)}
            </Select>
          </label>
        )}
        {project && (
          <div className="rounded-xl bg-success/5 p-3 text-sm">
            <div className="font-medium text-success">Draft “{project.name}” created</div>
            <Link href={`/websites/${project.id}`} className="mt-1 inline-block text-accent hover:underline">Open in Website Studio</Link>
          </div>
        )}
      </div>
    </Dialog>
  );
}

function ConsentDialog({ leadId, onClose, onDone }: { leadId: string; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [channel, setChannel] = useState<string>(CHANNELS[0]);
  const [basis, setBasis] = useState<string>(BASES[0]);
  const [evidence, setEvidence] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function save() {
    setBusy(true); setError(null);
    try {
      await compliance.createConsent({ lead_id: leadId, channel, basis, evidence_text: evidence.trim() || undefined, evidence_url: url.trim() || undefined });
      toast("Consent recorded", "success");
      onDone();
      onClose();
    } catch (e) { setError(e); } finally { setBusy(false); }
  }
  return (
    <Dialog open onClose={onClose} title="Add consent" description="Record the lawful basis and evidence for contacting this lead on a channel."
      footer={<>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button onClick={save} loading={busy} disabled={busy}>Save consent</Button>
      </>}>
      <div className="space-y-3 text-sm">
        <ErrorBox error={error} />
        <label className="block"><span className="mb-1 block text-xs text-muted">Channel</span>
          <Select value={channel} onChange={(e) => setChannel(e.target.value)} className="w-full">
            {CHANNELS.map((c) => <option key={c} value={c}>{human(c)}</option>)}
          </Select>
        </label>
        <label className="block"><span className="mb-1 block text-xs text-muted">Basis</span>
          <Select value={basis} onChange={(e) => setBasis(e.target.value)} className="w-full">
            {BASES.map((b) => <option key={b} value={b}>{human(b)}</option>)}
          </Select>
        </label>
        <label className="block"><span className="mb-1 block text-xs text-muted">Evidence</span>
          <Input value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="e.g. Signed form on 2026-11-01" maxLength={2000} />
        </label>
        <label className="block"><span className="mb-1 block text-xs text-muted">Evidence URL (optional)</span>
          <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" type="url" />
        </label>
      </div>
    </Dialog>
  );
}
