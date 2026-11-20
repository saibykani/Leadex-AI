"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Mail, Plus, Trash2 } from "lucide-react";
import { useSession } from "@/lib/session-context";
import { Alert, Button, EmptyState, Input } from "@/components/ui";
import {
  email, type EmailAccount, type EmailAnalytics, type EmailMessage, type EmailTemplate, type ProviderStatus,
} from "@/lib/communication";
import type { Page } from "@/lib/api";
import { Badge } from "../campaigns/_ui/badge";

export default function EmailPage() {
  const { can } = useSession();
  const [tab, setTab] = useState<"accounts" | "templates" | "messages">("accounts");
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Email</h1>
        <p className="mt-1 text-sm text-muted">Connected mailboxes, templates and every message with its compliance outcome.</p>
      </div>
      <div className="inline-flex rounded-full bg-raised p-1">
        {(["accounts", "templates", "messages"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`rounded-full px-4 py-1.5 text-sm capitalize transition ${tab === t ? "bg-white shadow-sm font-medium" : "text-muted"}`}>{t}</button>
        ))}
      </div>
      {error && <Alert>{error}</Alert>}
      {tab === "accounts" && <Accounts canManage={can("integrations:manage")} onError={setError} />}
      {tab === "templates" && <Templates canWrite={can("campaigns:write")} onError={setError} />}
      {tab === "messages" && <Messages onError={setError} />}
    </div>
  );
}

function Accounts({ canManage, onError }: { canManage: boolean; onError: (e: string | null) => void }) {
  const [accounts, setAccounts] = useState<EmailAccount[] | null>(null);
  const [providers, setProviders] = useState<ProviderStatus | null>(null);
  const [smtp, setSmtp] = useState("");
  const load = useCallback(() => {
    email.accounts().then(setAccounts).catch((e) => onError(e.message));
    email.providers().then(setProviders).catch((e) => onError(e.message));
  }, [onError]);
  useEffect(load, [load]);

  const connect = async (p: "gmail" | "outlook") => {
    onError(null);
    try { window.location.href = (await email.authorize(p)).authorization_url; } catch (e) { onError((e as Error).message); }
  };
  const addSmtp = async () => {
    onError(null);
    try { await email.addSmtp(smtp); setSmtp(""); load(); } catch (e) { onError((e as Error).message); }
  };

  return (
    <div className="space-y-4">
      {providers && (
        <div className="card flex flex-wrap items-center gap-3 p-4 text-sm">
          <span className="text-muted">Outbound mode:</span><Badge value={providers.outbound_mode} />
          <span className="ml-4 text-muted">Gmail</span><Badge value={providers.gmail} />
          <span className="text-muted">Outlook</span><Badge value={providers.outlook} />
          <span className="text-muted">SMTP</span><Badge value={providers.smtp} />
        </div>
      )}
      {canManage && (
        <div className="card space-y-3 p-5">
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={providers?.gmail !== "configured"} onClick={() => connect("gmail")}>Connect Gmail</Button>
            <Button variant="outline" disabled={providers?.outlook !== "configured"} onClick={() => connect("outlook")}>Connect Outlook</Button>
          </div>
          {providers && (providers.gmail !== "configured" || providers.outlook !== "configured") && (
            <p className="text-xs text-muted">Providers marked “not configured” need OAuth client credentials on the server before they can be connected.</p>
          )}
          <div className="flex gap-2">
            <Input placeholder="SMTP sender address" value={smtp} onChange={(e) => setSmtp(e.target.value)} />
            <Button onClick={addSmtp} disabled={!smtp}><Plus className="h-4 w-4" />Add</Button>
          </div>
        </div>
      )}
      {accounts?.length === 0 && <EmptyState icon={<Mail className="h-5 w-5" />} title="No mailboxes yet" body="Connect Gmail, Outlook or an SMTP sender. Nothing is sent until a campaign is approved and every recipient passes the compliance gate." />}
      {!!accounts?.length && (
        <ul className="card divide-y divide-line">
          {accounts.map((a) => (
            <li key={a.id} className="flex items-center justify-between px-5 py-3 text-sm">
              <div>
                <div className="font-medium">{a.address}</div>
                <div className="text-xs text-muted">{a.provider}{a.provider !== "smtp" && !a.credentials_encrypted ? " · credentials not encrypted" : ""}{a.last_error ? ` · ${a.last_error}` : ""}</div>
              </div>
              <div className="flex items-center gap-3">
                <Badge value={a.status} />
                {canManage && <button aria-label="Remove" className="text-muted hover:text-danger" onClick={() => email.removeAccount(a.id).then(load).catch((e) => onError(e.message))}><Trash2 className="h-4 w-4" /></button>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const STARTER = `<h2 style="margin:0 0 12px">Hi {{business_name}},</h2>
<p>We put together a free preview of a modern website for your business.</p>
<p><a href="{{website_preview_url}}" style="display:inline-block;background:#0071e3;color:#fff;padding:10px 18px;border-radius:999px;text-decoration:none">View your preview</a></p>`;

function Templates({ canWrite, onError }: { canWrite: boolean; onError: (e: string | null) => void }) {
  const [list, setList] = useState<EmailTemplate[]>([]);
  const [sel, setSel] = useState<EmailTemplate | null>(null);
  const [form, setForm] = useState({ name: "Intro", subject: "A website idea for {{business_name}}", html: STARTER, text: "Hi {{business_name}}, see your preview: {{website_preview_url}}" });
  const [preview, setPreview] = useState<string>("");
  const [missing, setMissing] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const load = useCallback(() => { email.templates().then(setList).catch((e) => onError(e.message)); }, [onError]);
  useEffect(load, [load]);
  useEffect(() => {
    const h = setTimeout(() => {
      email.preview({ subject: form.subject, html: form.html, text: form.text })
        .then((p) => { setPreview(p.html); setMissing(p.missing_variables); }).catch(() => {});
    }, 350);
    return () => clearTimeout(h);
  }, [form.subject, form.html, form.text]);

  const pick = (t: EmailTemplate | null) => {
    setSel(t);
    setForm(t ? { name: t.name, subject: t.subject, html: t.html, text: t.text ?? "" } : { name: "New template", subject: "", html: STARTER, text: "" });
  };
  const save = async () => {
    onError(null); setSaving(true);
    try {
      const saved = sel ? await email.updateTemplate(sel.id, form) : await email.createTemplate(form);
      setSel(saved); load();
    } catch (e) { onError((e as Error).message); } finally { setSaving(false); }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[220px_1fr_1fr]">
      <div className="card p-2">
        {canWrite && <button className="mb-1 w-full rounded-lg px-3 py-2 text-left text-sm text-accent hover:bg-raised" onClick={() => pick(null)}>+ New template</button>}
        {list.map((t) => (
          <button key={t.id} onClick={() => pick(t)} className={`w-full rounded-lg px-3 py-2 text-left text-sm ${sel?.id === t.id ? "bg-accent-soft font-medium" : "hover:bg-raised"}`}>{t.name}</button>
        ))}
      </div>
      <div className="card space-y-3 p-5">
        <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Name" />
        <Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder="Subject" />
        <textarea className="h-64 w-full rounded-xl border border-line p-3 font-mono text-xs outline-none focus:border-accent" value={form.html} onChange={(e) => setForm({ ...form, html: e.target.value })} />
        <textarea className="h-24 w-full rounded-xl border border-line p-3 text-sm outline-none focus:border-accent" placeholder="Plain-text version" value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} />
        <p className="text-xs text-muted">Variables: {"{{business_name}} {{city}} {{industry}} {{website}} {{website_preview_url}}"}. An unsubscribe link and your postal address are appended automatically.</p>
        {missing.length > 0 && <p className="text-xs text-amber-700">No sample value for: {missing.join(", ")}</p>}
        {canWrite && <Button onClick={save} loading={saving}>{sel ? "Save changes" : "Create template"}</Button>}
      </div>
      <div className="card overflow-hidden">
        <div className="border-b border-line px-4 py-2 text-xs text-muted">Preview (sample data)</div>
        <iframe title="Email preview" sandbox="" srcDoc={preview} className="h-[560px] w-full bg-white" />
      </div>
    </div>
  );
}

function Messages({ onError }: { onError: (e: string | null) => void }) {
  const [data, setData] = useState<Page<EmailMessage> | null>(null);
  const [stats, setStats] = useState<EmailAnalytics | null>(null);
  const [status, setStatus] = useState("");
  useEffect(() => {
    email.messages({ status }).then(setData).catch((e) => onError(e.message));
    email.analytics().then(setStats).catch(() => {});
  }, [status, onError]);
  return (
    <div className="space-y-4">
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {([["Sent", stats.sent], ["Delivered", stats.delivered], ["Bounced", stats.bounced], ["Replied", stats.replied], ["Simulated", stats.simulated], ["Blocked", stats.blocked], ["Inbound", stats.inbound]] as const).map(([l, v]) => (
            <div key={l} className="card p-4"><div className="text-xs text-muted">{l}</div><div className="mt-1 text-xl font-semibold">{v}</div></div>
          ))}
        </div>
      )}
      <select className="h-10 rounded-xl border border-line bg-white px-3 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">All statuses</option>
        {["simulated", "blocked", "sent", "delivered", "bounced", "replied", "failed", "received"].map((s) => <option key={s}>{s}</option>)}
      </select>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted"><tr><th className="px-4 py-2">When</th><th>To / From</th><th>Subject</th><th>Status</th><th>Reasons</th><th>Campaign</th></tr></thead>
          <tbody className="divide-y divide-line">
            {data?.items.map((m) => (
              <tr key={m.id}>
                <td className="whitespace-nowrap px-4 py-2 text-xs text-muted">{new Date(m.created_at).toLocaleString()}</td>
                <td className="text-xs">{m.direction === "inbound" ? `← ${m.from_address}` : `→ ${m.to_address ?? "—"}`}</td>
                <td className="max-w-[240px] truncate">{m.subject}</td>
                <td><Badge value={m.status} /></td>
                <td className="max-w-[260px] text-xs text-muted">{m.gate_reasons?.join(", ")}</td>
                <td className="text-xs">{m.campaign_id ? <Link className="text-accent" href={`/campaigns/${m.campaign_id}`}>open</Link> : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data?.items.length === 0 && <p className="px-4 py-8 text-center text-sm text-muted">No messages recorded yet.</p>}
      </div>
    </div>
  );
}
