"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { Globe, Plus, X } from "lucide-react";
import { useSession } from "@/lib/session-context";
import { Alert, Button, EmptyState, Input } from "@/components/ui";
import { STATUS_STYLE, websites, type Project, type Template } from "@/lib/websites";

function TemplateThumb({ t, selected, onClick }: { t: Template; selected?: boolean; onClick?: () => void }) {
  const th = t.theme;
  return (
    <button type="button" onClick={onClick}
      className={clsx("overflow-hidden rounded-xl border text-left transition-all", selected ? "border-accent ring-4 ring-accent/20" : "border-line hover:border-neutral-300")}>
      <div className="h-24 p-3" style={{ background: th.hero === "overlay" ? th.gradient : th.surface }}>
        <div className="flex h-full gap-2">
          <div className="flex flex-1 flex-col justify-center gap-1.5">
            <div className="h-2 w-3/4 rounded" style={{ background: th.hero === "overlay" ? "#fff" : th.text }} />
            <div className="h-1.5 w-1/2 rounded opacity-60" style={{ background: th.hero === "overlay" ? "#fff" : th.muted }} />
            <div className="mt-1 h-3 w-10" style={{ background: th.primary, borderRadius: th.radius }} />
          </div>
          {th.hero === "split" && <div className="w-1/3 rounded" style={{ background: th.gradient }} />}
        </div>
      </div>
      <div className="flex gap-1 px-3 pt-2">{[th.primary, th.accent, th.surface].map((c) => <span key={c} className="h-3 w-3 rounded-full border border-line" style={{ background: c }} />)}</div>
      <div className="px-3 pb-3 pt-1">
        <p className="text-sm font-medium">{t.name}</p>
        <p className="text-xs capitalize text-muted">{t.key.replace(/_/g, " ")} · {th.hero} hero</p>
      </div>
    </button>
  );
}

function CreateDialog({ templates, onClose }: { templates: Template[]; onClose: () => void }) {
  const router = useRouter();
  const [tpl, setTpl] = useState(templates.find((t) => t.key === "general_smb")?.key ?? templates[0]?.key ?? "general_smb");
  const [picked, setPicked] = useState(false);
  const [f, setF] = useState({ name: "", industry: "", tagline: "", description: "", services: "", city: "", address: "", phone: "", email: "", hours: "", whatsapp_number: "" });
  const [wa, setWa] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const clean = Object.fromEntries(Object.entries(f).filter(([, v]) => v.trim())) as Record<string, string>;
      const p = await websites.generate({
        template_key: tpl,
        business: { ...clean, name: f.name, services: f.services.split(",").map((s) => s.trim()).filter(Boolean), whatsapp_authorized: wa && !!f.whatsapp_number },
      });
      router.push(`/websites/${p.id}`);
    } catch (err) { setError((err as Error).message); setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm" role="dialog" aria-modal>
      <form onSubmit={submit} className="card max-h-[92vh] w-full max-w-4xl overflow-y-auto p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">New website</h2>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-full p-2 hover:bg-raised"><X className="h-4 w-4" /></button>
        </div>
        {error && <div className="mb-3"><Alert>{error}</Alert></div>}
        <p className="mb-2 text-sm font-medium">1. Choose a design</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {templates.map((t) => <TemplateThumb key={t.key} t={t} selected={t.key === tpl} onClick={() => { setTpl(t.key); setPicked(true); }} />)}
        </div>
        <p className="mb-2 mt-6 text-sm font-medium">2. Business facts</p>
        <p className="mb-3 text-xs text-muted">Only what you enter is used. Missing details appear as clearly marked “[Add your …]” placeholders; nothing is invented.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Input required placeholder="Business name *" value={f.name} onChange={set("name")} maxLength={200} />
          <Input placeholder="Industry" value={f.industry} onChange={(e) => {
            set("industry")(e);
            const q = e.target.value.toLowerCase().replace(/[^a-z]/g, "");
            const hit = q.length >= 4 && templates.find((t) => t.key.replace(/_/g, "").startsWith(q.slice(0, 6)) || t.name.toLowerCase().replace(/[^a-z]/g, "").includes(q));
            if (!picked && hit) setTpl(hit.key);
          }} />
          <Input placeholder="Tagline" value={f.tagline} onChange={set("tagline")} maxLength={200} />
          <Input placeholder="City" value={f.city} onChange={set("city")} />
          <Input placeholder="Phone" value={f.phone} onChange={set("phone")} />
          <Input placeholder="Email" type="email" value={f.email} onChange={set("email")} />
          <Input placeholder="Address" value={f.address} onChange={set("address")} />
          <Input placeholder="Opening hours" value={f.hours} onChange={set("hours")} />
          <Input placeholder="Services (comma separated)" value={f.services} onChange={set("services")} className="sm:col-span-2" />
          <textarea placeholder="Description" value={f.description} onChange={set("description")} maxLength={2000}
            className="min-h-24 rounded-xl border border-line px-4 py-3 text-[15px] outline-none focus:border-accent sm:col-span-2" />
          <Input placeholder="WhatsApp number" value={f.whatsapp_number} onChange={set("whatsapp_number")} />
          <label className="flex items-center gap-2 text-sm text-muted">
            <input type="checkbox" checked={wa} onChange={(e) => setWa(e.target.checked)} /> Business authorised a WhatsApp link
          </label>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={busy} disabled={!f.name.trim()}>Generate website</Button>
        </div>
      </form>
    </div>
  );
}

export default function WebsitesPage() {
  const { can, current } = useSession();
  const [items, setItems] = useState<Project[] | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const allowed = can("websites:write");

  useEffect(() => {
    if (!allowed) return;
    websites.list().then((p) => setItems(p.items)).catch((e) => setError(e.message));
    websites.templates().then(setTemplates).catch((e) => setError(e.message));
  }, [allowed, current.organization.id]);

  if (!allowed) return <EmptyState icon={<Globe className="h-5 w-5" />} title="No access" body="You need the websites:write permission to view websites." />;
  const byKey = Object.fromEntries(templates.map((t) => [t.key, t]));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Websites</h1>
          <p className="mt-1 text-sm text-muted">Generate, review and publish sites for your businesses.</p>
        </div>
        <Button onClick={() => setOpen(true)} disabled={!templates.length}><Plus className="h-4 w-4" /> New website</Button>
      </div>
      {error && <Alert>{error}</Alert>}
      {items && items.length === 0 && <EmptyState icon={<Globe className="h-5 w-5" />} title="No websites yet" body="Create your first website from one of 11 industry templates." />}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {items?.map((p) => {
          const th = byKey[p.template_key]?.theme;
          return (
            <Link key={p.id} href={`/websites/${p.id}`} className="card overflow-hidden transition-shadow hover:shadow-lg">
              <div className="h-28" style={{ background: th?.gradient ?? "linear-gradient(135deg,#0a84ff,#5e5ce6)" }} />
              <div className="p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate font-medium">{p.name}</p>
                  <span className={clsx("rounded-full px-2 py-0.5 text-xs font-medium capitalize", STATUS_STYLE[p.status])}>{p.status}</span>
                </div>
                <p className="mt-1 text-xs text-muted">{byKey[p.template_key]?.name ?? p.template_key} · updated {new Date(p.updated_at).toLocaleDateString()}</p>
              </div>
            </Link>
          );
        })}
      </div>
      {open && <CreateDialog templates={templates} onClose={() => setOpen(false)} />}
    </div>
  );
}
