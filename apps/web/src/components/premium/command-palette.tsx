"use client";
import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight, Bot, Building2, CornerDownLeft, Globe2, Loader2, Megaphone, Plus, Search, Sparkles, Users, Wand2,
  type LucideIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, type Page } from "@/lib/api";
import { useSession } from "@/lib/session-context";

export type NavEntry = { href: string; label: string; icon: LucideIcon; group: string };
type Hit = { id: string; label: string; sub?: string; href: string; icon: LucideIcon; group: string };

const Ctx = createContext<{ open: () => void }>({ open: () => {} });
export const useCommandPalette = () => useContext(Ctx);

const ACTIONS: (Hit & { perm?: string })[] = [
  { id: "a-copilot", label: "Ask your pipeline (Copilot)", href: "/copilot", icon: Sparkles, group: "Quick actions", perm: "leads:read" },
  { id: "a-lead", label: "New lead", href: "/leads?new=1", icon: Plus, group: "Quick actions", perm: "leads:write" },
  { id: "a-disc", label: "Run discovery search", href: "/discovery", icon: Search, group: "Quick actions", perm: "discovery:run" },
  { id: "a-site", label: "Generate website", href: "/websites", icon: Wand2, group: "Quick actions", perm: "websites:write" },
  { id: "a-camp", label: "New campaign", href: "/campaigns/new", icon: Megaphone, group: "Quick actions", perm: "campaigns:write" },
];

function useDebounced<T>(v: T, ms: number) {
  const [d, setD] = useState(v);
  useEffect(() => { const t = setTimeout(() => setD(v), ms); return () => clearTimeout(t); }, [v, ms]);
  return d;
}

export function CommandPaletteProvider({ nav, children }: { nav: NavEntry[]; children: ReactNode }) {
  const [isOpen, setOpen] = useState(false);
  const open = useCallback(() => setOpen(true), []);
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);
  return (
    <Ctx.Provider value={{ open }}>
      {children}
      <AnimatePresence>{isOpen && <Palette nav={nav} onClose={() => setOpen(false)} />}</AnimatePresence>
    </Ctx.Provider>
  );
}

function Palette({ nav, onClose }: { nav: NavEntry[]; onClose: () => void }) {
  const router = useRouter();
  const { can } = useSession();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const [remote, setRemote] = useState<Hit[]>([]);
  const [loading, setLoading] = useState(false);
  const dq = useDebounced(q.trim(), 200);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => { inputRef.current?.focus(); }, []);

  // Live search across existing list endpoints (tenant-scoped, permission-aware).
  useEffect(() => {
    if (dq.length < 2) { setRemote([]); return; }
    let live = true;
    setLoading(true);
    const enc = encodeURIComponent(dq);
    const low = dq.toLowerCase();
    const jobs: Promise<Hit[]>[] = [];
    if (can("leads:read")) jobs.push(api<Page<{ id: string; business_name: string; city: string | null; status: string }>>(`/leads?q=${enc}&page_size=5`, {}, true)
      .then((p) => p.items.map((l) => ({ id: `l${l.id}`, label: l.business_name, sub: [l.status.replace(/_/g, " "), l.city].filter(Boolean).join(" · "), href: `/leads/${l.id}`, icon: Users, group: "Leads" }))));
    if (can("businesses:read")) jobs.push(api<Page<{ id: string; name: string | null; city: string | null }>>(`/businesses?q=${enc}&page_size=5`, {}, true)
      .then((p) => p.items.map((b) => ({ id: `b${b.id}`, label: b.name ?? "(unnamed)", sub: b.city ?? undefined, href: `/businesses/${b.id}`, icon: Building2, group: "Businesses" }))));
    if (can("websites:write")) jobs.push(api<Page<{ id: string; name: string; status: string }>>(`/websites?page_size=100`, {}, true)
      .then((p) => p.items.filter((w) => w.name.toLowerCase().includes(low)).slice(0, 5)
        .map((w) => ({ id: `w${w.id}`, label: w.name, sub: w.status, href: `/websites/${w.id}`, icon: Globe2, group: "Websites" }))));
    if (can("agents:read")) jobs.push(api<Page<{ id: string; name: string; status: string }>>(`/agents?page_size=100`, {}, true)
      .then((p) => p.items.filter((a) => a.name.toLowerCase().includes(low)).slice(0, 5)
        .map((a) => ({ id: `g${a.id}`, label: a.name, sub: a.status, href: `/agents/${a.id}`, icon: Bot, group: "Agents" }))));
    Promise.all(jobs.map((j) => j.catch(() => [] as Hit[]))).then((r) => { if (live) { setRemote(r.flat()); setLoading(false); } });
    return () => { live = false; };
  }, [dq, can]);

  const hits = useMemo(() => {
    const low = q.trim().toLowerCase();
    const actions = ACTIONS.filter((a) => (!a.perm || can(a.perm)) && (!low || a.label.toLowerCase().includes(low)));
    const pages = nav.filter((n) => !low || n.label.toLowerCase().includes(low) || n.group.toLowerCase().includes(low))
      .slice(0, low ? 8 : 6).map((n) => ({ id: `n${n.href}`, label: n.label, sub: n.group, href: n.href, icon: n.icon, group: "Go to" }));
    if (low && q.trim().length > 3) actions.push({ id: "a-ask", label: `Ask Copilot: “${q.trim()}”`, href: `/copilot?q=${encodeURIComponent(q.trim())}`, icon: Sparkles, group: "Quick actions" });
    return [...remote, ...actions, ...pages];
  }, [q, remote, nav, can]);

  useEffect(() => { setSel(0); }, [q, remote.length]);
  useEffect(() => { listRef.current?.querySelector(`[data-idx="${sel}"]`)?.scrollIntoView({ block: "nearest" }); }, [sel]);

  const go = (h: Hit | undefined) => { if (!h) return; onClose(); router.push(h.href); };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(s + 1, hits.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); go(hits[sel]); }
    else if (e.key === "Escape") { e.preventDefault(); onClose(); }
  };

  let idx = -1;
  const groups = hits.reduce<Record<string, Hit[]>>((acc, h) => { (acc[h.group] ??= []).push(h); return acc; }, {});
  return (
    <motion.div className="fixed inset-0 z-[70] flex items-start justify-center px-4 pt-[12vh]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }}>
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <motion.div role="dialog" aria-modal="true" aria-label="Command palette" onKeyDown={onKey}
        initial={{ opacity: 0, y: -12, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.98 }}
        transition={{ type: "spring", damping: 30, stiffness: 420 }}
        className="ring-gradient glass relative w-full max-w-xl overflow-hidden rounded-2xl border border-line shadow-lift">
        <div className="flex items-center gap-3 border-b border-line px-4">
          {loading ? <Loader2 className="h-5 w-5 animate-spin text-accent" /> : <Search className="h-5 w-5 text-muted" />}
          <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search leads, businesses, websites, agents… or jump anywhere"
            aria-label="Search" role="combobox" aria-expanded="true" aria-controls="cmdk-list"
            className="h-14 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-muted" />
          <kbd className="kbd">Esc</kbd>
        </div>
        <div ref={listRef} id="cmdk-list" role="listbox" className="max-h-[52vh] overflow-y-auto p-2">
          {hits.length === 0 && !loading && <div className="px-4 py-10 text-center text-sm text-muted">No matches for “{q}”.</div>}
          {Object.entries(groups).map(([g, items]) => (
            <div key={g} className="mb-1">
              <div className="eyebrow px-3 pb-1 pt-2">{g}</div>
              {items.map((h) => {
                idx += 1;
                const i = idx;
                const on = i === sel;
                return (
                  <button key={h.id} data-idx={i} role="option" aria-selected={on} onMouseMove={() => setSel(i)} onClick={() => go(h)}
                    className={clsx("relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm", on ? "text-ink" : "text-neutral-700")}>
                    {on && <motion.span layoutId="cmdk-sel" className="absolute inset-0 rounded-xl bg-accent/10" transition={{ type: "spring", damping: 35, stiffness: 500 }} />}
                    <span className={clsx("relative grid h-8 w-8 shrink-0 place-items-center rounded-lg ring-1 ring-inset", on ? "bg-brand text-white ring-transparent" : "bg-raised text-muted ring-line")}><h.icon className="h-4 w-4" /></span>
                    <span className="relative min-w-0 flex-1"><span className="block truncate font-medium">{h.label}</span>{h.sub && <span className="block truncate text-xs capitalize text-muted">{h.sub}</span>}</span>
                    {on && <ArrowRight className="relative h-4 w-4 text-accent" />}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
        <div className="flex items-center gap-4 border-t border-line px-4 py-2 text-[11px] text-muted">
          <span className="flex items-center gap-1"><kbd className="kbd">↑</kbd><kbd className="kbd">↓</kbd> navigate</span>
          <span className="flex items-center gap-1"><kbd className="kbd"><CornerDownLeft className="h-3 w-3" /></kbd> open</span>
          <span className="ml-auto">Results are live from your workspace</span>
        </div>
      </motion.div>
    </motion.div>
  );
}
