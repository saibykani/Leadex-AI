"use client";
import { useCallback, useEffect, useState } from "react";
import { Check, Download, ImageIcon, Trash2, Upload, X } from "lucide-react";
import { Alert, Badge, Button } from "@/components/ui";
import { pipelineApi, type BusinessImage, type GooglePhoto, type Outcome } from "@/lib/pipeline";

const money = (o: Outcome) => {
  const c = o.budget_currency ?? "";
  const f = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (o.budget_min != null && o.budget_max != null) return o.budget_min === o.budget_max ? `${c} ${f(o.budget_min)}` : `${c} ${f(o.budget_min)}–${f(o.budget_max)}`;
  if (o.budget_max != null) return `up to ${c} ${f(o.budget_max)}`;
  if (o.budget_min != null) return `at least ${c} ${f(o.budget_min)}`;
  return null;
};
const interestTone = { high: "success", medium: "accent", low: "warning", none: "danger", unknown: "neutral" } as const;

export function OutcomeCard({ o }: { o: Outcome }) {
  const budget = money(o);
  return (
    <div className="card space-y-3 p-5 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">Conversation outcome</h3>
        <Badge tone={interestTone[o.interest]}>Interest: {o.interest}</Badge>
        <Badge tone={o.extraction_mode === "llm" ? "violet" : "neutral"}>extraction: {o.extraction_mode}{o.model ? ` (${o.model})` : ""}</Badge>
        {o.simulated && <Badge tone="warning">simulated</Badge>}
      </div>
      <dl className="grid gap-3 sm:grid-cols-2">
        <div><dt className="text-muted">Budget</dt><dd className="font-medium">{budget ?? "Not stated by the prospect"}</dd>
          {o.budget_evidence && <dd className="mt-1 text-xs italic text-muted">“{o.budget_evidence}”</dd>}</div>
        <div><dt className="text-muted">Timeline</dt><dd className="font-medium">{o.timeline ?? "Not stated"}</dd>
          {o.timeline_evidence && <dd className="mt-1 text-xs italic text-muted">“{o.timeline_evidence}”</dd>}</div>
        <div><dt className="text-muted">Decision maker</dt><dd className="font-medium">{o.decision_maker ?? "Unknown"}</dd>
          {o.decision_maker_evidence && <dd className="mt-1 text-xs italic text-muted">“{o.decision_maker_evidence}”</dd>}</div>
        <div><dt className="text-muted">Next step</dt><dd className="font-medium">{o.next_step ?? "None agreed"}</dd></div>
      </dl>
      {!!o.objections?.length && (
        <div><p className="text-muted">Objections</p>
          <ul className="mt-1 space-y-1">{o.objections.map((x, i) => <li key={i}><b>{x.objection.replace(/_/g, " ")}</b> <span className="text-xs italic text-muted">“{x.evidence}”</span></li>)}</ul></div>
      )}
      <p className="rounded-xl bg-raised p-3">{o.summary}</p>
      {o.warnings?.length > 0 && <p className="text-xs text-muted">Notes: {o.warnings.join("; ")}</p>}
    </div>
  );
}

function useObjectUrl(load: () => Promise<string>) {
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let u: string | null = null; let alive = true;
    load().then((x) => { u = x; if (alive) setUrl(x); else URL.revokeObjectURL(x); }).catch((e) => alive && setErr((e as Error).message));
    return () => { alive = false; if (u) URL.revokeObjectURL(u); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return { url, err };
}

function GoogleTile({ bid, p }: { bid: string; p: GooglePhoto }) {
  const { url, err } = useObjectUrl(() => pipelineApi.googlePhotoUrl(bid, p.name));
  return (
    <figure className="overflow-hidden rounded-xl border border-line">
      <div className="flex aspect-[4/3] items-center justify-center bg-raised">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {url ? <img src={url} alt="Google Maps photo" className="h-full w-full object-cover" /> : <span className="px-2 text-center text-xs text-muted">{err ?? "Loading…"}</span>}
      </div>
      <figcaption className="p-2 text-xs text-muted">
        Photo: {p.attributions.length ? p.attributions.map((a, i) => (
          <span key={i}>{i > 0 && ", "}{a.uri ? <a className="text-accent" href={a.uri} target="_blank" rel="noopener noreferrer">{a.display_name ?? "contributor"}</a> : a.display_name}</span>
        )) : "Google contributor"} · Google Maps
      </figcaption>
    </figure>
  );
}

export function GooglePhotos({ businessId }: { businessId: string }) {
  const [photos, setPhotos] = useState<GooglePhoto[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { pipelineApi.googlePhotos(businessId).then((r) => setPhotos(r.photos)).catch((e) => setErr(e.message)); }, [businessId]);
  if (err) return <Alert>{err}</Alert>;
  if (!photos) return <p className="text-sm text-muted">Loading Google photos…</p>;
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted">Google Maps photos are shown here for review only, with attribution. They are not stored and are <b>never copied into generated websites</b> (Google Maps Platform terms).</p>
      {photos.length === 0 ? <p className="text-sm text-muted">No Google photo references (not a Google Places result, not requested, or retention expired).</p> : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{photos.map((p) => <GoogleTile key={p.name} bid={businessId} p={p} />)}</div>
      )}
    </div>
  );
}

function OwnedTile({ bid, img, selected, onSelect, onChange }: {
  bid: string; img: BusinessImage; selected?: boolean; onSelect?: (on: boolean) => void; onChange: () => void;
}) {
  const { url } = useObjectUrl(() => pipelineApi.imageUrl(bid, img.id));
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const act = async (fn: () => Promise<unknown>) => { setBusy(true); try { await fn(); onChange(); } finally { setBusy(false); } };
  return (
    <figure className={`overflow-hidden rounded-xl border ${selected ? "border-accent ring-2 ring-accent/30" : "border-line"}`}>
      <div className="flex aspect-[4/3] items-center justify-center bg-raised">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {url ? <img src={url} alt={img.alt ?? ""} className="h-full w-full object-cover" /> : <ImageIcon className="h-6 w-6 text-muted" />}
      </div>
      <figcaption className="space-y-2 p-2 text-xs">
        <div className="flex flex-wrap gap-1">
          <Badge tone={img.source === "owner_supplied" ? "accent" : "violet"}>{img.source === "owner_supplied" ? "owner supplied" : "from business website"}</Badge>
          <Badge tone={img.status === "approved" ? "success" : img.status === "rejected" ? "danger" : "warning"}>{img.status.replace("_", " ")}</Badge>
        </div>
        {img.origin_url && <p className="truncate text-muted" title={img.origin_url}>{img.origin_url}</p>}
        {img.status === "pending_review" && (
          <div className="space-y-1">
            <label className="flex items-start gap-1"><input type="checkbox" checked={ok} onChange={(e) => setOk(e.target.checked)} />I have permission to use this image</label>
            <div className="flex gap-1">
              <Button variant="outline" disabled={!ok || busy} onClick={() => act(() => pipelineApi.approve(bid, img.id))}><Check className="h-3 w-3" />Approve</Button>
              <Button variant="outline" disabled={busy} onClick={() => act(() => pipelineApi.reject(bid, img.id))}><X className="h-3 w-3" />Reject</Button>
            </div>
          </div>
        )}
        <div className="flex items-center justify-between">
          {onSelect && img.usable_in_website ? (
            <label className="flex items-center gap-1"><input type="checkbox" checked={!!selected} onChange={(e) => onSelect(e.target.checked)} />Use in website</label>
          ) : <span />}
          <button aria-label="Delete image" className="text-muted hover:text-danger" disabled={busy} onClick={() => act(() => pipelineApi.remove(bid, img.id))}><Trash2 className="h-3.5 w-3.5" /></button>
        </div>
      </figcaption>
    </figure>
  );
}

export function BusinessImages({ businessId, hasWebsite, selected, onSelectedChange }: {
  businessId: string; hasWebsite: boolean; selected?: string[]; onSelectedChange?: (ids: string[]) => void;
}) {
  const [imgs, setImgs] = useState<BusinessImage[]>([]);
  const [perm, setPerm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => pipelineApi.images(businessId).then(setImgs).catch((e) => setErr(e.message)), [businessId]);
  useEffect(() => { load(); }, [load]);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true); setErr(null); setMsg(null);
    try {
      for (const f of Array.from(files)) {
        if (f.size > 5 * 1024 * 1024) throw new Error(`${f.name}: larger than 5 MB`);
        await pipelineApi.upload(businessId, f, perm);
      }
      await load();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  async function importSite() {
    setBusy(true); setErr(null); setMsg(null);
    try {
      const r = await pipelineApi.importWebsite(businessId);
      setMsg(`Imported ${r.imported.length} image(s) for review; skipped ${r.skipped.length}. ${r.notice}`);
      await load();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  const sel = selected ?? [];
  return (
    <div className="space-y-3">
      {err && <Alert>{err}</Alert>}
      {msg && <p className="rounded-xl bg-raised p-3 text-sm">{msg}</p>}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2"><input type="checkbox" checked={perm} onChange={(e) => setPerm(e.target.checked)} />I have permission to use these images</label>
        <label className={`inline-flex h-9 cursor-pointer items-center gap-2 rounded-full border border-line px-4 ${!perm || busy ? "pointer-events-none opacity-50" : "hover:bg-raised"}`}>
          <Upload className="h-4 w-4" />Upload PNG/JPG/WEBP (≤ 5 MB)
          <input type="file" accept="image/png,image/jpeg,image/webp" multiple className="sr-only" disabled={!perm || busy} onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
        </label>
        {hasWebsite && <Button variant="outline" loading={busy} onClick={importSite}><Download className="h-4 w-4" />Find images on their website</Button>}
      </div>
      {imgs.length === 0 ? <p className="text-sm text-muted">No business images yet. Without images the generated website uses its styled no-photo design.</p> : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {imgs.map((i) => <OwnedTile key={i.id} bid={businessId} img={i} onChange={load}
            selected={sel.includes(i.id)}
            onSelect={onSelectedChange ? (on) => onSelectedChange(on ? [...sel, i.id] : sel.filter((x) => x !== i.id)) : undefined} />)}
        </div>
      )}
    </div>
  );
}
