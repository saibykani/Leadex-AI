"use client";
import { useEffect, useState } from "react";
import { Palette } from "lucide-react";
import { applyBrand, brandingApi, type Brand } from "@/lib/branding";
import { useSession } from "@/lib/session-context";
import { Alert, Button, Input, PageHeader, Skeleton, useToast } from "@/components/ui";

export default function BrandingPage() {
  const { can } = useSession();
  const toast = useToast();
  const [b, setB] = useState<Brand | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { brandingApi.get().then(setB).catch((e) => setError((e as Error).message)); }, []);
  const set = <K extends keyof Brand>(k: K, v: Brand[K]) => setB((x) => (x ? { ...x, [k]: v } : x));

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!b) return;
    setBusy(true); setError(null);
    try {
      const saved = await brandingApi.save({
        app_name: b.app_name || null, logo_url: b.logo_url || null, primary_color: b.primary_color || null,
        support_email: b.support_email || null, app_domain: b.app_domain || null, hide_powered_by: b.hide_powered_by,
      });
      setB(saved); applyBrand(saved); toast("Branding saved", "success");
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  if (!can("org:write")) return <Alert>Only Owners and Admins can change branding.</Alert>;
  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Branding" description="White label: show your own name, logo and colour to your team and clients." />
      {error && <Alert>{error}</Alert>}
      {!b ? <Skeleton className="h-80 w-full" /> : (
        <form onSubmit={save} className="card space-y-5 p-6">
          <h2 className="flex items-center gap-2 text-[15px] font-semibold"><Palette className="h-4 w-4 text-accent" />Brand</h2>
          <div><label className="label" htmlFor="b-name">App name</label>
            <Input id="b-name" maxLength={80} placeholder="e.g. GrowthPro CRM" value={b.app_name ?? ""} onChange={(e) => set("app_name", e.target.value)} /></div>
          <div><label className="label" htmlFor="b-logo">Logo URL (https, square image works best)</label>
            <Input id="b-logo" placeholder="https://yourdomain.com/logo.png" value={b.logo_url ?? ""} onChange={(e) => set("logo_url", e.target.value)} /></div>
          <div className="flex items-end gap-3">
            <div className="flex-1"><label className="label" htmlFor="b-color">Main colour</label>
              <Input id="b-color" placeholder="#0071e3" value={b.primary_color ?? ""} onChange={(e) => set("primary_color", e.target.value)} /></div>
            <input type="color" aria-label="Pick colour" value={b.primary_color || "#0071e3"} onChange={(e) => set("primary_color", e.target.value)} className="h-12 w-14 cursor-pointer rounded-xl border border-line bg-surface" />
          </div>
          <div><label className="label" htmlFor="b-mail">Support email shown to your users</label>
            <Input id="b-mail" type="email" value={b.support_email ?? ""} onChange={(e) => set("support_email", e.target.value)} /></div>
          <div><label className="label" htmlFor="b-domain">Custom app domain</label>
            <Input id="b-domain" placeholder="app.yourbrand.com" value={b.app_domain ?? ""} onChange={(e) => set("app_domain", e.target.value)} />
            <p className="mt-1 text-xs text-muted">Point a CNAME record for this domain at your Leadex server. The sign-in page on that domain then shows your brand. HTTPS is issued automatically by the server (see the deployment guide).</p></div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={b.hide_powered_by} onChange={(e) => set("hide_powered_by", e.target.checked)} />Hide “Powered by Leadex”</label>
          <Button type="submit" loading={busy}>Save branding</Button>
        </form>
      )}
    </div>
  );
}
