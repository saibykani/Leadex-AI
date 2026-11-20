"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import clsx from "clsx";
import { ArrowLeft, Check, Copy, History, Laptop, MessageSquare, Smartphone, Tablet, Trash2, Plus } from "lucide-react";
import { useSession } from "@/lib/session-context";
import { Alert, Badge, Button, Input } from "@/components/ui";
import {
  STATUS_STYLE, absolute, websites,
  type Content, type Deployment, type DomainInfo, type Feedback, type ProjectDetail, type Section, type Version,
} from "@/lib/websites";

const DEVICES = { desktop: { w: "100%", icon: Laptop }, tablet: { w: "820px", icon: Tablet }, mobile: { w: "390px", icon: Smartphone } } as const;
type Device = keyof typeof DEVICES;

const field = "w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/15";

function SectionEditor({ s, onChange }: { s: Section; onChange: (s: Section) => void }) {
  const items = s.items ?? [];
  const setItem = (i: number, k: "title" | "description", v: string) => onChange({ ...s, items: items.map((it, j) => (j === i ? { ...it, [k]: v } : it)) });
  return (
    <div className="space-y-2">
      <input className={field} value={s.heading} maxLength={200} onChange={(e) => onChange({ ...s, heading: e.target.value })} placeholder="Heading" />
      {s.type !== "gallery" && (
        <textarea className={clsx(field, "min-h-20")} value={s.body ?? ""} maxLength={5000} onChange={(e) => onChange({ ...s, body: e.target.value })} placeholder="Text" />
      )}
      {(s.type === "hero" || s.type === "cta") && (
        <input className={field} value={s.cta_label ?? ""} maxLength={60} onChange={(e) => onChange({ ...s, cta_label: e.target.value })} placeholder="Button label" />
      )}
      {(s.type === "services" || s.type === "gallery") && (
        <div className="space-y-2">
          {items.map((it, i) => (
            <div key={i} className="rounded-lg bg-raised p-2">
              <div className="flex gap-2">
                <input className={field} value={it.title ?? ""} maxLength={200} onChange={(e) => setItem(i, "title", e.target.value)} placeholder={s.type === "gallery" ? "Caption" : "Title"} />
                <button type="button" aria-label="Remove item" className="rounded p-2 text-muted hover:text-danger" onClick={() => onChange({ ...s, items: items.filter((_, j) => j !== i) })}><Trash2 className="h-4 w-4" /></button>
              </div>
              {s.type === "services" && <textarea className={clsx(field, "mt-2 min-h-14")} value={it.description ?? ""} maxLength={1000} onChange={(e) => setItem(i, "description", e.target.value)} placeholder="Description" />}
            </div>
          ))}
          {items.length < 24 && (
            <button type="button" className="inline-flex items-center gap-1 text-sm text-accent" onClick={() => onChange({ ...s, items: [...items, { title: "", description: "" }] })}>
              <Plus className="h-4 w-4" /> Add item
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function DomainCard({ id, canPublish }: { id: string; canPublish: boolean }) {
  const [info, setInfo] = useState<DomainInfo | null>(null);
  const [domain, setDomain] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { websites.domain(id).then(setInfo).catch((e) => setErr(e.message)); }, [id]);
  async function act(label: string, fn: () => Promise<DomainInfo | undefined>) {
    setBusy(label); setErr(null);
    try { const r = await fn(); setInfo(r ?? { domain: null, status: "none", verified_at: null, record_type: "TXT", record_name: null, record_value: null, message: null }); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  }
  const tone = info?.status === "verified" ? "success" : info?.status === "pending" ? "warning" : "neutral";
  return (
    <div className="card space-y-3 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Custom domain</h2>
        {info?.domain && <Badge tone={tone}>{info.status === "verified" ? "Verified" : "Pending verification"}</Badge>}
      </div>
      {err && <Alert>{err}</Alert>}
      {!info?.domain ? (
        <div className="flex flex-wrap gap-2">
          <Input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="www.yourbusiness.com" maxLength={255} className="flex-1" disabled={!canPublish} />
          <Button loading={busy === "set"} disabled={!canPublish || domain.trim().length < 3} onClick={() => act("set", () => websites.setDomain(id, domain.trim()))}>Connect</Button>
        </div>
      ) : (
        <div className="space-y-2 text-sm">
          <p>Domain: <code className="rounded bg-raised px-1.5 py-0.5">{info.domain}</code></p>
          {info.status !== "verified" && (
            <div className="rounded-lg bg-raised p-3 text-xs">
              <p className="mb-1">Add this DNS record at your domain provider, then click Verify:</p>
              <p>Type: <b>{info.record_type}</b></p>
              <p className="break-all">Name: <code>{info.record_name}</code></p>
              <p className="break-all">Value: <code>{info.record_value}</code></p>
            </div>
          )}
          {info.status === "verified" && <p className="text-xs text-muted">Point a CNAME (or A record) for this domain at your LEADEX hosting address to go live. The site is served once published.</p>}
          {info.message && <p className="text-xs text-muted">{info.message}</p>}
          {canPublish && (
            <div className="flex gap-2">
              {info.status !== "verified" && <Button size="sm" loading={busy === "verify"} onClick={() => act("verify", () => websites.verifyDomain(id))}>Verify</Button>}
              <Button size="sm" variant="outline" loading={busy === "remove"} onClick={() => { if (window.confirm("Remove this custom domain? The site will stop being served on it.")) void act("remove", async () => { await websites.removeDomain(id); return undefined; }); }}>Remove</Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function WebsiteEditor() {
  const { id } = useParams<{ id: string }>();
  const { can } = useSession();
  const [p, setP] = useState<ProjectDetail | null>(null);
  const [content, setContent] = useState<Content | null>(null);
  const [html, setHtml] = useState("");
  const [dirty, setDirty] = useState(false);
  const [device, setDevice] = useState<Device>("desktop");
  const [versions, setVersions] = useState<Version[]>([]);
  const [feedback, setFeedback] = useState<Feedback[]>([]);
  const [deploys, setDeploys] = useState<Deployment[]>([]);
  const [tab, setTab] = useState<"content" | "business" | "seo">("content");
  const [open, setOpen] = useState<number | null>(0);
  const [note, setNote] = useState("");
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const canPublish = can("websites:publish");

  const loadSide = useCallback(() => {
    websites.versions(id).then(setVersions).catch(() => {});
    websites.feedback(id).then(setFeedback).catch(() => {});
    websites.deployments(id).then(setDeploys).catch(() => {});
  }, [id]);

  const apply = useCallback((d: ProjectDetail) => { setP(d); setContent(d.content); setHtml(d.rendered_html ?? ""); setDirty(false); }, []);

  useEffect(() => { websites.get(id).then(apply).catch((e) => setError(e.message)); loadSide(); }, [id, apply, loadSide]);

  function edit(next: Content) {
    setContent(next); setDirty(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { websites.render(id, next).then(setHtml).catch(() => {}); }, 400);
  }

  async function run(label: string, fn: () => Promise<unknown>, confirmMsg?: string) {
    if (confirmMsg && !window.confirm(confirmMsg)) return;
    setBusy(label); setError(null);
    try { await fn(); loadSide(); } catch (e) { setError((e as Error).message); } finally { setBusy(null); }
  }

  if (!p || !content) return <div className="text-sm text-muted">{error ? <Alert>{error}</Alert> : "Loading…"}</div>;
  const setSection = (i: number, s: Section) => edit({ ...content, sections: content.sections.map((x, j) => (j === i ? s : x)) });
  const move = (i: number, d: -1 | 1) => {
    const arr = [...content.sections]; const j = i + d;
    if (j < 0 || j >= arr.length) return;
    [arr[i], arr[j]] = [arr[j], arr[i]]; edit({ ...content, sections: arr });
  };
  const biz = content.business;
  const placeholders = (JSON.stringify(content).match(/\[Add your [^\]]*\]/g) ?? []).length;
  const phWarn = placeholders ? `

Warning: ${placeholders} "[Add your …]" placeholder${placeholders > 1 ? "s are" : " is"} still in the content and will appear on the site.` : "";
  const setBiz = (k: keyof typeof biz, v: string | boolean) => edit({ ...content, business: { ...biz, [k]: v } });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link href="/websites" className="rounded-full p-2 hover:bg-raised" aria-label="Back"><ArrowLeft className="h-4 w-4" /></Link>
          <div>
            <h1 className="text-lg font-semibold">{p.name}</h1>
            <p className="text-xs text-muted">v{p.current_version_number} · {p.generation_mode === "ai" ? "AI-assisted copy" : p.generation_mode === "template" ? "Template copy" : p.generation_mode}
              <span className={clsx("ml-2 rounded-full px-2 py-0.5 font-medium capitalize", STATUS_STYLE[p.status])}>{p.status}</span></p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" loading={busy === "share"} onClick={() => run("share", async () => { const l = await websites.previewLink(id); setShareUrl(absolute(l.path)); setP({ ...p, status: p.status === "draft" ? "preview" : p.status }); })}>Share preview</Button>
          {canPublish && <Button variant="outline" loading={busy === "approve"} disabled={dirty || p.status === "approved" || p.status === "published"} onClick={() => run("approve", async () => apply(await websites.approve(id)), `Approve version ${p.current_version_number} for publishing?${phWarn}`)}>Approve</Button>}
          {canPublish && <Button loading={busy === "publish"} disabled={dirty || p.status !== "approved"} onClick={() => run("publish", async () => { await websites.publish(id); apply(await websites.get(id)); }, `Publish this approved version to the live site?${phWarn}`)}>Publish</Button>}
        </div>
      </div>
      {error && <Alert>{error}</Alert>}
      {shareUrl && (
        <div className="card flex flex-wrap items-center gap-2 p-3 text-sm">
          <span className="text-muted">Preview link (noindex):</span>
          <code className="flex-1 truncate rounded bg-raised px-2 py-1">{shareUrl}</code>
          <button className="inline-flex items-center gap-1 text-accent" onClick={() => { void navigator.clipboard.writeText(shareUrl); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />} {copied ? "Copied" : "Copy"}</button>
          <button className="text-muted hover:text-danger" onClick={() => run("rotate", async () => { const l = await websites.previewLink(id, true); setShareUrl(absolute(l.path)); }, "Revoke the current link and create a new one?")}>Revoke &amp; regenerate</button>
        </div>
      )}
      {placeholders > 0 && <Alert tone="info">{placeholders} “[Add your …]” placeholder{placeholders > 1 ? "s" : ""} still need real details before this site goes live.</Alert>}
      <DomainCard id={id} canPublish={canPublish} />
      {p.published_path && <p className="text-sm text-muted">Live (local hosting): <a className="text-accent underline" href={absolute(p.published_path)} target="_blank" rel="noreferrer">{absolute(p.published_path)}</a></p>}

      <div className="grid gap-4 lg:grid-cols-[340px_1fr_260px]">
        {/* Editor */}
        <div className="card space-y-3 p-4 lg:max-h-[78vh] lg:overflow-y-auto">
          <div className="flex gap-1 rounded-full bg-raised p-1 text-sm">
            {(["content", "business", "seo"] as const).map((t) => (
              <button key={t} onClick={() => setTab(t)} className={clsx("flex-1 rounded-full py-1.5 capitalize", tab === t && "bg-white shadow-sm")}>{t}</button>
            ))}
          </div>
          {tab === "content" && content.sections.map((s, i) => (
            <div key={i} className="rounded-xl border border-line">
              <div className="flex items-center gap-2 px-3 py-2">
                <input type="checkbox" checked={s.enabled} aria-label={`Show ${s.type}`} onChange={(e) => setSection(i, { ...s, enabled: e.target.checked })} />
                <button className="flex-1 text-left text-sm font-medium capitalize" onClick={() => setOpen(open === i ? null : i)}>{s.type}</button>
                <button className="text-muted" aria-label="Move up" onClick={() => move(i, -1)}>↑</button>
                <button className="text-muted" aria-label="Move down" onClick={() => move(i, 1)}>↓</button>
              </div>
              {open === i && <div className="border-t border-line p-3"><SectionEditor s={s} onChange={(x) => setSection(i, x)} /></div>}
            </div>
          ))}
          {tab === "business" && (
            <div className="space-y-2">
              {(["name", "industry_label", "tagline", "description", "city", "address", "phone", "email", "hours", "whatsapp_number"] as const).map((k) => (
                <label key={k} className="block text-xs text-muted">{k.replace(/_/g, " ")}
                  <input className={clsx(field, "mt-1")} value={(biz[k] as string | null) ?? ""} onChange={(e) => setBiz(k, e.target.value)} />
                </label>
              ))}
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={biz.whatsapp_authorized} onChange={(e) => setBiz("whatsapp_authorized", e.target.checked)} /> WhatsApp link authorised by business</label>
            </div>
          )}
          {tab === "seo" && (
            <div className="space-y-2">
              <label className="block text-xs text-muted">Title<input className={clsx(field, "mt-1")} maxLength={120} value={content.seo.title} onChange={(e) => edit({ ...content, seo: { ...content.seo, title: e.target.value } })} /></label>
              <label className="block text-xs text-muted">Description<textarea className={clsx(field, "mt-1 min-h-20")} maxLength={300} value={content.seo.description} onChange={(e) => edit({ ...content, seo: { ...content.seo, description: e.target.value } })} /></label>
            </div>
          )}
          <div className="sticky bottom-0 space-y-2 border-t border-line bg-surface pt-3">
            <Input placeholder="Version note (optional)" value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} className="h-10" />
            <Button className="w-full" disabled={!dirty} loading={busy === "save"} onClick={() => run("save", async () => { apply(await websites.save(id, { content, note: note || undefined })); setNote(""); })}>
              {dirty ? "Save as new version" : "Saved"}</Button>
          </div>
        </div>

        {/* Preview */}
        <div className="card flex flex-col p-3">
          <div className="mb-2 flex justify-center gap-1">
            {(Object.keys(DEVICES) as Device[]).map((d) => {
              const Icon = DEVICES[d].icon;
              return <button key={d} onClick={() => setDevice(d)} aria-label={d} className={clsx("rounded-full p-2", device === d ? "bg-accent text-white" : "text-muted hover:bg-raised")}><Icon className="h-4 w-4" /></button>;
            })}
          </div>
          <div className="flex flex-1 justify-center overflow-auto rounded-xl bg-raised p-2">
            <iframe title="Website preview" srcDoc={html} sandbox="" className="h-[72vh] rounded-lg border border-line bg-white transition-all" style={{ width: DEVICES[device].w, maxWidth: "100%" }} />
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <div className="card p-4">
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><History className="h-4 w-4" /> Versions</h3>
            <ul className="max-h-72 space-y-1 overflow-y-auto text-sm">
              {versions.map((v) => {
                const live = v.id === p.published_version_id;
                const wasDeployed = deploys.some((d) => d.version_id === v.id);
                return (
                  <li key={v.id} className="rounded-lg px-2 py-1.5 hover:bg-raised">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">v{v.number}{v.id === p.current_version_id && <span className="ml-1 text-xs text-muted">(current)</span>}{live && <span className="ml-1 text-xs text-green-700">live</span>}</span>
                      <span className="text-xs text-muted">{new Date(v.created_at).toLocaleString()}</span>
                    </div>
                    <p className="truncate text-xs text-muted">{v.note ?? v.generation_mode}</p>
                    <div className="mt-1 flex gap-3 text-xs">
                      {v.id !== p.current_version_id && <button className="text-accent" onClick={() => run("restore", async () => apply(await websites.restore(id, v.id)), `Restore v${v.number} as a new draft version?`)}>Restore</button>}
                      {canPublish && wasDeployed && !live && <button className="text-amber-700" onClick={() => run("rollback", async () => { await websites.rollback(id, v.id); apply(await websites.get(id)); }, `Roll the live site back to v${v.number}?`)}>Roll back live site</button>}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
          <div className="card p-4">
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><MessageSquare className="h-4 w-4" /> Feedback</h3>
            {feedback.length === 0 && <p className="text-xs text-muted">No feedback yet. Share the preview link to collect comments.</p>}
            <ul className="space-y-2 text-sm">
              {feedback.map((f) => (
                <li key={f.id} className="rounded-lg bg-raised p-2">
                  <div className="flex items-center justify-between"><span className="font-medium">{f.name}</span>{f.approved && <span className="rounded-full bg-green-50 px-2 text-xs text-green-700">Approved</span>}</div>
                  <p className="whitespace-pre-wrap text-xs text-muted">{f.message}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
