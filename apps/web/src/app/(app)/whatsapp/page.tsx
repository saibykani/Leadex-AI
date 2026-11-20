"use client";
import { useCallback, useEffect, useState } from "react";
import { MessageCircle, Send, UserRound } from "lucide-react";
import { useSession } from "@/lib/session-context";
import { Alert, Button, EmptyState, Input } from "@/components/ui";
import { whatsapp, type Conversation, type WAAccount, type WAMessage, type WATemplate } from "@/lib/communication";
import { Badge } from "../campaigns/_ui/badge";

export default function WhatsAppPage() {
  const [tab, setTab] = useState<"inbox" | "templates">("inbox");
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">WhatsApp</h1>
        <p className="mt-1 text-sm text-muted">Official WhatsApp Cloud API inbox. Business-initiated messages require an approved template.</p>
      </div>
      <div className="inline-flex rounded-full bg-raised p-1">
        {(["inbox", "templates"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`rounded-full px-4 py-1.5 text-sm capitalize ${tab === t ? "bg-white font-medium shadow-sm" : "text-muted"}`}>{t}</button>
        ))}
      </div>
      {error && <Alert>{error}</Alert>}
      {tab === "inbox" ? <Inbox onError={setError} /> : <Templates onError={setError} />}
    </div>
  );
}

function Inbox({ onError }: { onError: (e: string | null) => void }) {
  const { can } = useSession();
  const [convs, setConvs] = useState<Conversation[] | null>(null);
  const [active, setActive] = useState<Conversation | null>(null);
  const [msgs, setMsgs] = useState<WAMessage[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const loadConvs = useCallback(() => { whatsapp.conversations().then((p) => setConvs(p.items)).catch((e) => onError(e.message)); }, [onError]);
  useEffect(loadConvs, [loadConvs]);
  useEffect(() => { if (active) whatsapp.messages(active.id).then(setMsgs).catch((e) => onError(e.message)); }, [active, onError]);

  const send = async () => {
    if (!active || !text.trim()) return;
    onError(null); setSending(true);
    try { const m = await whatsapp.send(active.id, { text }); setMsgs((x) => [...x, m]); setText(""); }
    catch (e) { onError((e as Error).message); } finally { setSending(false); }
  };
  const toggleHandoff = async () => {
    if (!active) return;
    const c = await whatsapp.patch(active.id, { handoff_to_human: !active.handoff_to_human }).catch((e) => { onError(e.message); return null; });
    if (c) { setActive(c); loadConvs(); }
  };

  if (convs && convs.length === 0) {
    return <EmptyState icon={<MessageCircle className="h-5 w-5" />} title="No conversations yet" body="Inbound WhatsApp messages appear here once a phone number is connected and Meta delivers webhooks to this server." />;
  }
  return (
    <div className="card grid min-h-[520px] overflow-hidden md:grid-cols-[280px_1fr]">
      <ul className="divide-y divide-line border-b border-line md:border-b-0 md:border-r">
        {convs?.map((c) => (
          <li key={c.id}>
            <button onClick={() => setActive(c)} className={`w-full px-4 py-3 text-left ${active?.id === c.id ? "bg-accent-soft" : "hover:bg-raised"}`}>
              <div className="flex items-center justify-between text-sm font-medium">
                <span>{c.contact_name ?? `+${c.contact_phone}`}</span>
                {c.opted_out ? <Badge value="unsubscribed" /> : c.handoff_to_human ? <span className="h-2 w-2 rounded-full bg-accent" title="Needs a human" /> : null}
              </div>
              <div className="text-xs text-muted">{c.last_message_at ? new Date(c.last_message_at).toLocaleString() : ""}</div>
            </button>
          </li>
        ))}
      </ul>
      <div className="flex flex-col">
        {!active ? <div className="m-auto text-sm text-muted">Select a conversation</div> : (
          <>
            <div className="flex items-center justify-between border-b border-line px-5 py-3">
              <div className="text-sm font-medium">{active.contact_name ?? `+${active.contact_phone}`}{!active.lead_id && <span className="ml-2 text-xs text-amber-700">not linked to a lead — replies are blocked</span>}</div>
              <Button variant="outline" className="h-8 px-3 text-xs" onClick={toggleHandoff}><UserRound className="h-3.5 w-3.5" />{active.handoff_to_human ? "Return to AI" : "Take over"}</Button>
            </div>
            <div className="flex-1 space-y-2 overflow-y-auto bg-raised/40 p-5">
              {msgs.map((m) => (
                <div key={m.id} className={`flex ${m.direction === "outbound" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[75%] rounded-2xl px-3.5 py-2 text-sm ${m.direction === "outbound" ? "bg-accent text-white" : "bg-white"}`}>
                    <div>{m.body}</div>
                    {m.direction === "outbound" && (
                      <div className="mt-1 text-[11px] opacity-80">{m.status}{m.gate_reasons?.length ? ` · ${m.gate_reasons.join(", ")}` : ""}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
            {can("leads:write") && (
              <div className="flex gap-2 border-t border-line p-3">
                <Input value={text} onChange={(e) => setText(e.target.value)} placeholder={active.opted_out ? "Contact opted out" : "Reply (24-hour window)"} disabled={active.opted_out}
                  onKeyDown={(e) => { if (e.key === "Enter") void send(); }} />
                <Button onClick={send} loading={sending} disabled={active.opted_out}><Send className="h-4 w-4" /></Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Templates({ onError }: { onError: (e: string | null) => void }) {
  const { can } = useSession();
  const [list, setList] = useState<WATemplate[]>([]);
  const [accounts, setAccounts] = useState<WAAccount[]>([]);
  const [form, setForm] = useState({ name: "", language: "en_US", category: "marketing", body: "" });
  const [phoneId, setPhoneId] = useState("");
  const load = useCallback(() => {
    whatsapp.templates().then(setList).catch((e) => onError(e.message));
    whatsapp.accounts().then(setAccounts).catch(() => {});
  }, [onError]);
  useEffect(load, [load]);
  const create = async () => {
    onError(null);
    try { await whatsapp.createTemplate(form); setForm({ ...form, name: "", body: "" }); load(); } catch (e) { onError((e as Error).message); }
  };
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-4">
        {can("integrations:manage") && (
          <div className="card space-y-2 p-5">
            <h2 className="text-sm font-medium">Phone numbers</h2>
            {accounts.map((a) => <div key={a.id} className="flex justify-between text-sm"><span>{a.display_phone ?? a.phone_number_id}</span><Badge value={a.status} /></div>)}
            <div className="flex gap-2"><Input placeholder="Phone number ID (from Meta)" value={phoneId} onChange={(e) => setPhoneId(e.target.value)} />
              <Button onClick={() => whatsapp.addAccount(phoneId).then(() => { setPhoneId(""); load(); }).catch((e) => onError(e.message))} disabled={!phoneId}>Add</Button></div>
          </div>
        )}
        {can("campaigns:write") && (
          <div className="card space-y-2 p-5">
            <h2 className="text-sm font-medium">New template</h2>
            <Input placeholder="name_in_snake_case" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <div className="flex gap-2">
              <Input value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })} />
              <select className="h-12 rounded-xl border border-line bg-white px-3 text-sm" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                <option>marketing</option><option>utility</option><option>authentication</option>
              </select>
            </div>
            <textarea className="h-28 w-full rounded-xl border border-line p-3 text-sm" placeholder="Hi {{1}}, …" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
            <p className="text-xs text-muted">Submit the template in WhatsApp Manager, then record Meta’s decision here. Only approved templates can start conversations.</p>
            <Button onClick={create} disabled={!form.name || !form.body}>Create</Button>
          </div>
        )}
      </div>
      <ul className="card divide-y divide-line self-start">
        {list.map((t) => (
          <li key={t.id} className="space-y-1 px-5 py-3">
            <div className="flex items-center justify-between"><span className="text-sm font-medium">{t.name} <span className="text-xs text-muted">{t.language} · {t.category}</span></span><Badge value={t.status} /></div>
            <p className="text-sm text-muted">{t.body}</p>
            {can("integrations:manage") && (
              <div className="flex gap-2 pt-1">
                {(["approved", "rejected", "pending"] as const).filter((s) => s !== t.status).map((s) => (
                  <button key={s} className="text-xs text-accent" onClick={() => whatsapp.setTemplateStatus(t.id, s).then(load).catch((e) => onError(e.message))}>Mark {s}</button>
                ))}
              </div>
            )}
          </li>
        ))}
        {list.length === 0 && <li className="px-5 py-8 text-center text-sm text-muted">No templates yet.</li>}
      </ul>
    </div>
  );
}
