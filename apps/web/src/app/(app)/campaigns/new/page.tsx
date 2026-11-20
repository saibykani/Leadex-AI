"use client";
import { agentsApi, type Agent } from "@/lib/agents";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Alert, Button, Input } from "@/components/ui";
import {
  campaigns, email, whatsapp, type Channel, type EmailAccount, type EmailStep, type EmailTemplate, type WATemplate,
} from "@/lib/communication";

const STEPS = ["Basics", "Content", "Recipients", "Review"] as const;

export default function NewCampaign() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [channel, setChannel] = useState<Channel>("email");
  const [spendLimit, setSpendLimit] = useState("");
  const [sendWindow, setWindow] = useState({ enabled: false, start_hour: 9, end_hour: 18 });
  const [accounts, setAccounts] = useState<EmailAccount[]>([]);
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [waTemplates, setWaTemplates] = useState<WATemplate[]>([]);
  const [accountId, setAccountId] = useState("");
  const [steps, setSteps] = useState<EmailStep[]>([]);
  const [address, setAddress] = useState("");
  const [previewBase, setPreviewBase] = useState("");
  const [waTemplateId, setWaTemplateId] = useState("");
  const [voiceAgents, setVoiceAgents] = useState<Agent[]>([]);
  const [voiceAgentId, setVoiceAgentId] = useState("");
  const [maxCalls, setMaxCalls] = useState(3);
  useEffect(() => { agentsApi.list().then((p) => setVoiceAgents(p.items)).catch(() => {}); }, []);
  const [leadIds, setLeadIds] = useState("");
  const [filterStatus, setFilterStatus] = useState("approved_for_outreach");
  const [filterCity, setFilterCity] = useState("");

  useEffect(() => {
    email.accounts().then(setAccounts).catch(() => {});
    email.templates().then(setTemplates).catch(() => {});
    whatsapp.templates().then(setWaTemplates).catch(() => {});
  }, []);

  const create = async () => {
    setError(null); setBusy(true);
    try {
      const c = await campaigns.create({
        name, channel, spend_limit: spendLimit || null,
        send_window: sendWindow.enabled ? { start_hour: sendWindow.start_hour, end_hour: sendWindow.end_hour } : null,
        whatsapp_template_id: channel === "whatsapp" ? waTemplateId || null : null,
        ...(channel === "voice" ? { voice_agent_id: voiceAgentId || null, max_concurrent_calls: maxCalls } : {}),
        email: channel === "email" ? { account_id: accountId || null, steps, physical_address: address || null, website_preview_base_url: previewBase || null, personalize_with_ai: false } : undefined,
      });
      const ids = leadIds.split(/[\s,]+/).filter(Boolean);
      await campaigns.addRecipients(c.id, ids.length ? { lead_ids: ids } : { filter_status: filterStatus ? [filterStatus] : undefined, filter_city: filterCity || undefined });
      router.push(`/campaigns/${c.id}`);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold">New campaign</h1>
      <ol className="flex gap-2 text-xs">
        {STEPS.map((s, i) => <li key={s} className={`rounded-full px-3 py-1 ${i === step ? "bg-accent text-white" : i < step ? "bg-accent-soft text-accent" : "bg-raised text-muted"}`}>{i + 1}. {s}</li>)}
      </ol>
      {error && <Alert>{error}</Alert>}
      <div className="card space-y-4 p-6">
        {step === 0 && (<>
          <label className="block text-sm">Name<Input value={name} onChange={(e) => setName(e.target.value)} className="mt-1" /></label>
          <div className="flex gap-2">
            {(["email", "whatsapp", "voice"] as const).map((c) => (
              <button key={c} onClick={() => setChannel(c)} className={`flex-1 rounded-xl border px-4 py-3 text-sm capitalize ${channel === c ? "border-accent bg-accent-soft font-medium" : "border-line"}`}>{c}</button>
            ))}
          </div>
          <label className="block text-sm">Spend limit (optional)<Input type="number" min="0" value={spendLimit} onChange={(e) => setSpendLimit(e.target.value)} className="mt-1" /></label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={sendWindow.enabled} onChange={(e) => setWindow({ ...sendWindow, enabled: e.target.checked })} />Restrict send window (UTC hours)</label>
          {sendWindow.enabled && (
            <div className="flex gap-2">
              <Input type="number" min={0} max={23} value={sendWindow.start_hour} onChange={(e) => setWindow({ ...sendWindow, start_hour: +e.target.value })} />
              <Input type="number" min={0} max={24} value={sendWindow.end_hour} onChange={(e) => setWindow({ ...sendWindow, end_hour: +e.target.value })} />
            </div>
          )}
        </>)}
        {step === 1 && channel === "email" && (<>
          <label className="block text-sm">Sender
            <select className="mt-1 h-12 w-full rounded-xl border border-line bg-white px-3" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              <option value="">— none (messages will be simulated) —</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.address} ({a.status})</option>)}
            </select>
          </label>
          <div className="space-y-2">
            <div className="text-sm">Sequence</div>
            {steps.map((s, i) => (
              <div key={i} className="flex gap-2">
                <select className="h-11 flex-1 rounded-xl border border-line bg-white px-3 text-sm" value={s.template_id} onChange={(e) => setSteps(steps.map((x, j) => j === i ? { ...x, template_id: e.target.value } : x))}>
                  {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
                <Input type="number" min={0} className="h-11 w-28" value={s.delay_hours} onChange={(e) => setSteps(steps.map((x, j) => j === i ? { ...x, delay_hours: +e.target.value } : x))} />
                <span className="self-center text-xs text-muted">{i === 0 ? "h (initial)" : "h after previous"}</span>
              </div>
            ))}
            <Button variant="outline" disabled={!templates.length} onClick={() => setSteps([...steps, { template_id: templates[0].id, delay_hours: steps.length ? 48 : 0 }])}>Add step</Button>
            {!templates.length && <p className="text-xs text-muted">Create an email template first.</p>}
          </div>
          <label className="block text-sm">Physical mailing address (required by CAN-SPAM)<Input value={address} onChange={(e) => setAddress(e.target.value)} className="mt-1" /></label>
          <label className="block text-sm">Website preview URL (use {"{lead_id}"})<Input value={previewBase} onChange={(e) => setPreviewBase(e.target.value)} className="mt-1" placeholder="https://preview.example/{lead_id}" /></label>
        </>)}
        {step === 1 && channel === "whatsapp" && (
          <label className="block text-sm">Approved template
            <select className="mt-1 h-12 w-full rounded-xl border border-line bg-white px-3" value={waTemplateId} onChange={(e) => setWaTemplateId(e.target.value)}>
              <option value="">Select…</option>
              {waTemplates.map((t) => <option key={t.id} value={t.id} disabled={t.status !== "approved"}>{t.name} ({t.status})</option>)}
            </select>
          </label>
        )}
        {step === 1 && channel === "voice" && (<div className="space-y-4">
          <p className="text-sm text-muted">The AI agent calls every lead in this campaign. Each call is checked again for consent, suppression and calling hours before it is dialled; blocked leads are skipped.</p>
          <label className="block text-sm">AI voice agent
            <select className="mt-1 h-12 w-full rounded-xl border border-line bg-white px-3" value={voiceAgentId} onChange={(e) => setVoiceAgentId(e.target.value)}>
              <option value="">Select…</option>
              {voiceAgents.map((a) => <option key={a.id} value={a.id} disabled={a.status !== "published"}>{a.name}{a.status !== "published" ? " (not published)" : ""}</option>)}
            </select>
          </label>
          <label className="block text-sm">Calls at the same time: <b>{maxCalls}</b>
            <input type="range" min={1} max={20} value={maxCalls} onChange={(e) => setMaxCalls(Number(e.target.value))} className="mt-2 w-full" />
            <span className="text-xs text-muted">Higher = faster campaigns. Your Twilio account limits how many calls it allows at once.</span>
          </label>
        </div>)}
        {step === 2 && (<>
          <label className="block text-sm">Lead IDs (comma or newline separated)
            <textarea className="mt-1 h-28 w-full rounded-xl border border-line p-3 font-mono text-xs" value={leadIds} onChange={(e) => setLeadIds(e.target.value)} />
          </label>
          <p className="text-xs text-muted">Or leave empty and use a filter:</p>
          <div className="flex gap-2">
            <Input placeholder="Lead status" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} />
            <Input placeholder="City" value={filterCity} onChange={(e) => setFilterCity(e.target.value)} />
          </div>
        </>)}
        {step === 3 && (
          <dl className="grid grid-cols-[140px_1fr] gap-y-2 text-sm">
            <dt className="text-muted">Name</dt><dd>{name}</dd>
            <dt className="text-muted">Channel</dt><dd className="capitalize">{channel}</dd>
            {channel === "email" && <><dt className="text-muted">Steps</dt><dd>{steps.length}</dd><dt className="text-muted">Address</dt><dd>{address || <span className="text-danger">missing</span>}</dd></>}
            <dt className="text-muted">Recipients</dt><dd>{leadIds.trim() ? `${leadIds.split(/[\s,]+/).filter(Boolean).length} lead IDs` : `filter: ${filterStatus || "any"} ${filterCity}`}</dd>
          </dl>
        )}
      </div>
      <div className="flex justify-between">
        <Button variant="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</Button>
        {step < 3 ? <Button disabled={step === 0 && !name.trim()} onClick={() => setStep(step + 1)}>Continue</Button>
          : <Button loading={busy} onClick={create}>Create draft</Button>}
      </div>
    </div>
  );
}
