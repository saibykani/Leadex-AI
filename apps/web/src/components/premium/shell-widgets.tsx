"use client";
import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { Bell, CheckCheck, FlaskConical, Keyboard, Moon, Sun, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Page } from "@/lib/api";
import { growth } from "@/lib/growth";
import { useSession } from "@/lib/session-context";
import { timeAgo } from "@/lib/crm";
import { useTheme } from "@/components/ui";

export function useOutside(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) close(); };
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    document.addEventListener("mousedown", h);
    document.addEventListener("keydown", k);
    return () => { document.removeEventListener("mousedown", h); document.removeEventListener("keydown", k); };
  }, [open, close]);
  return ref;
}

export const popover = {
  initial: { opacity: 0, y: -6, scale: 0.98 }, animate: { opacity: 1, y: 0, scale: 1 }, exit: { opacity: 0, y: -4, scale: 0.98 },
  transition: { type: "spring" as const, damping: 30, stiffness: 420 },
};

/* ------------------------------------------------------------------ theme toggle */
export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button onClick={toggle} aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"} title="Toggle theme"
      className="relative grid h-10 w-10 place-items-center overflow-hidden rounded-full text-muted transition hover:bg-raised hover:text-ink focus-ring">
      <AnimatePresence mode="wait" initial={false}>
        <motion.span key={theme} initial={{ rotate: -90, opacity: 0, scale: 0.6 }} animate={{ rotate: 0, opacity: 1, scale: 1 }} exit={{ rotate: 90, opacity: 0, scale: 0.6 }} transition={{ duration: 0.2 }}>
          {theme === "dark" ? <Moon className="h-[18px] w-[18px]" /> : <Sun className="h-[18px] w-[18px]" />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}

/* ------------------------------------------------------------------ notifications */
type Notification = { id: string; kind: string; title: string; body: string | null; read_at: string | null; created_at: string };
export function NotificationBell() {
  const { current } = useSession();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Page<Notification> | null>(null);
  const [err, setErr] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const ref = useOutside(open, close);
  const load = useCallback(() => api<Page<Notification>>("/notifications?page_size=12", {}, true).then((d) => { setData(d); setErr(false); }).catch(() => setErr(true)), []);
  useEffect(() => { void load(); const t = setInterval(load, 60_000); return () => clearInterval(t); }, [load, current.organization.id]);
  const unread = data?.items.filter((n) => !n.read_at).length ?? 0;
  const markAll = async () => {
    const items = data?.items.filter((n) => !n.read_at) ?? [];
    await Promise.all(items.map((n) => api(`/notifications/${n.id}/read`, { method: "POST" }, true).catch(() => null)));
    void load();
  };
  return (
    <div ref={ref} className="relative">
      <button onClick={() => { setOpen((o) => !o); if (!open) void load(); }} aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`} aria-expanded={open}
        className="relative grid h-10 w-10 place-items-center rounded-full text-muted transition hover:bg-raised hover:text-ink focus-ring">
        <Bell className="h-[18px] w-[18px]" />
        {unread > 0 && (
          <span className="absolute right-1.5 top-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-danger px-1 text-[10px] font-bold text-white ring-2 ring-surface">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div {...popover} className="glass absolute right-0 z-40 mt-2 w-[min(22rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-line shadow-lift">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <span className="text-sm font-semibold">Notifications</span>
              {unread > 0 && <button onClick={markAll} className="flex items-center gap-1 text-xs font-medium text-accent hover:underline"><CheckCheck className="h-3.5 w-3.5" />Mark all read</button>}
            </div>
            <ul className="max-h-96 overflow-y-auto">
              {err && <li className="px-4 py-8 text-center text-sm text-muted">Couldn&apos;t load notifications.</li>}
              {!err && data && data.items.length === 0 && (
                <li className="flex flex-col items-center px-4 py-10 text-center text-sm text-muted">
                  <span className="mb-2 grid h-10 w-10 place-items-center rounded-full bg-accent/10 text-accent"><Bell className="h-4 w-4" /></span>
                  You&apos;re all caught up.
                </li>
              )}
              {data?.items.map((n) => (
                <li key={n.id} className="flex gap-3 border-b border-line/60 px-4 py-3 last:border-0">
                  <span className={clsx("mt-1.5 h-2 w-2 shrink-0 rounded-full", n.read_at ? "bg-line" : "bg-accent")} />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{n.title}</div>
                    {n.body && <div className="line-clamp-2 text-xs text-muted">{n.body}</div>}
                    <div className="mt-0.5 text-[11px] text-muted">{timeAgo(n.created_at)}</div>
                  </div>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ------------------------------------------------------------------ keyboard shortcuts */
const SHORTCUTS: [string[], string][] = [
  [["Ctrl", "K"], "Open command palette"],
  [["?"], "Show keyboard shortcuts"],
  [["G", "D"], "Go to dashboard"],
  [["G", "L"], "Go to leads"],
  [["G", "I"], "Go to insights"],
  [["G", "C"], "Go to copilot"],
  [["G", "P"], "Go to pipeline"],
  [["["], "Collapse / expand sidebar"],
  [["Esc"], "Close dialogs & menus"],
];
const GOTO: Record<string, string> = { d: "/dashboard", l: "/leads", i: "/insights", c: "/copilot", p: "/pipeline", w: "/websites", a: "/agents" };

function typing(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null;
  return !!t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
}

export function useGlobalShortcuts(toggleSidebar: () => void) {
  const router = useRouter();
  const [help, setHelp] = useState(false);
  useEffect(() => {
    let g = 0;
    const h = (e: KeyboardEvent) => {
      if (typing(e) || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "?") { e.preventDefault(); setHelp((x) => !x); return; }
      if (e.key === "[") { toggleSidebar(); return; }
      if (e.key.toLowerCase() === "g") { g = Date.now(); return; }
      if (Date.now() - g < 900 && GOTO[e.key.toLowerCase()]) { router.push(GOTO[e.key.toLowerCase()]); g = 0; }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [router, toggleSidebar]);
  return { help, setHelp };
}

export function ShortcutsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[70] grid place-items-center p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
          <motion.div role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" initial={{ scale: 0.96, y: 10 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.97, opacity: 0 }}
            className="relative w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-lift">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="flex items-center gap-2 font-semibold"><Keyboard className="h-4 w-4 text-accent" />Keyboard shortcuts</h2>
              <button onClick={onClose} aria-label="Close" className="rounded-full p-1.5 text-muted hover:bg-raised"><X className="h-4 w-4" /></button>
            </div>
            <ul className="space-y-2">
              {SHORTCUTS.map(([keys, label]) => (
                <li key={label} className="flex items-center justify-between text-sm">
                  <span className="text-neutral-700">{label}</span>
                  <span className="flex gap-1">{keys.map((k) => <kbd key={k} className="kbd">{k}</kbd>)}</span>
                </li>
              ))}
            </ul>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ------------------------------------------------------------------ demo banner */
export function DemoBanner() {
  const { current } = useSession();
  const [isDemo, setIsDemo] = useState(false);
  useEffect(() => {
    let live = true;
    setIsDemo(false);
    growth.demoCurrent().then((r) => { if (live) setIsDemo(r.is_demo); }).catch(() => {});
    return () => { live = false; };
  }, [current.organization.id]);
  if (!isDemo) return null;
  return (
    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} role="status"
      className="relative overflow-hidden bg-[linear-gradient(90deg,#f59e0b,#f97316,#ef4444,#f59e0b)] bg-[length:200%_100%] text-white animate-gradient">
      <div className="flex items-center justify-center gap-2 px-4 py-1.5 text-center text-[13px] font-medium">
        <FlaskConical className="h-4 w-4 shrink-0" />
        <span><b>Demo workspace — fictional data.</b><span className="hidden sm:inline"> Companies, people and numbers here are invented for product demos.</span></span>
        <Link href="/demo" className="ml-1 shrink-0 underline underline-offset-2 hover:no-underline">Manage</Link>
      </div>
    </motion.div>
  );
}
