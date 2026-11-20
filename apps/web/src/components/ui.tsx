"use client";
import clsx from "clsx";
import { animate, AnimatePresence, motion, useInView, useReducedMotion } from "framer-motion";
import { AlertCircle, CheckCircle2, Info, Loader2, X } from "lucide-react";
import Link from "next/link";
import { useBrand } from "@/lib/branding";
import {
  createContext, forwardRef, useCallback, useContext, useEffect, useId, useRef, useState,
  type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes,
} from "react";

/* ------------------------------------------------------------------ buttons & inputs */
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "outline" | "gradient" | "soft"; loading?: boolean; size?: "sm" | "md" | "lg";
};
type BtnStyle = { variant?: BtnProps["variant"]; size?: BtnProps["size"]; className?: string };
function btnClass({ variant = "primary", size = "md", className }: BtnStyle) {
  return clsx(
        "group/btn relative inline-flex select-none items-center justify-center gap-2 overflow-hidden rounded-full font-medium",
        "transition-[transform,background-color,box-shadow,color,border-color] duration-150 ease-out focus-ring",
        "active:scale-[0.97] disabled:pointer-events-none disabled:opacity-50",
        size === "sm" && "h-9 px-4 text-[13px]",
        size === "md" && "h-11 px-6 text-[15px]",
        size === "lg" && "h-12 px-7 text-[15px]",
        variant === "primary" && "bg-accent text-white shadow-sm hover:-translate-y-px hover:bg-accent-strong hover:shadow-glow",
        variant === "gradient" && "bg-brand text-white shadow-glow hover:-translate-y-px hover:brightness-110",
        variant === "outline" && "border border-line bg-surface text-ink hover:-translate-y-px hover:border-accent/30 hover:bg-raised",
        variant === "soft" && "bg-accent/10 text-accent hover:bg-accent/15",
        variant === "ghost" && "text-muted hover:bg-raised hover:text-ink",
        className,
  );
}
const Shine = ({ variant = "primary" }: BtnStyle) => (variant === "primary" || variant === "gradient") ? (
  <span aria-hidden className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 group-hover/btn:translate-x-full" />
) : null;

export function Button({ variant = "primary", loading, size = "md", className, children, disabled, ...p }: BtnProps) {
  return (
    <button {...p} disabled={disabled || loading} className={btnClass({ variant, size, className })}>
      <Shine variant={variant} />
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

/** A link styled as a button (avoids invalid <a><button> nesting). */
export function LinkButton({ href, variant, size, className, children }: BtnStyle & { href: string; children: ReactNode }) {
  return (
    <Link href={href} className={btnClass({ variant, size, className })}>
      <Shine variant={variant} />
      {children}
    </Link>
  );
}

const field = "w-full rounded-xl border bg-surface text-ink outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-muted/70 focus:border-accent focus:ring-4 focus:ring-accent/15";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { error?: string }>(
  function Input({ className, error, ...p }, ref) {
    return (
      <>
        <input ref={ref} {...p} aria-invalid={error ? true : p["aria-invalid"]}
          className={clsx(field, "h-12 px-4 text-[15px]", error ? "border-danger" : "border-line hover:border-muted/40", className)} />
        {error && <p className="mt-1 text-xs text-danger">{error}</p>}
      </>
    );
  },
);

export function Alert({ children, tone = "danger" }: { children: ReactNode; tone?: "danger" | "info" | "success" }) {
  return (
    <motion.div role="alert" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
      className={clsx("flex items-start gap-2 rounded-xl border px-3 py-2 text-sm",
        tone === "danger" && "border-danger/30 bg-danger/10 text-danger",
        tone === "info" && "border-accent/25 bg-accent/10 text-accent",
        tone === "success" && "border-success/30 bg-success/10 text-success")}>
      {tone === "danger" ? <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> : tone === "success" ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <Info className="mt-0.5 h-4 w-4 shrink-0" />}
      <div className="min-w-0">{children}</div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ empty states */
/** Inline illustration: soft gradient orb + floating cards. Pure SVG, theme-aware via currentColor/tokens. */
export function EmptyIllustration({ className }: { className?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg viewBox="0 0 160 110" className={clsx("h-24 w-36", className)} aria-hidden>
      <defs>
        <linearGradient id={`g${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#0a84ff" /><stop offset=".55" stopColor="#5e5ce6" /><stop offset="1" stopColor="#bf5af2" />
        </linearGradient>
      </defs>
      <circle cx="80" cy="56" r="44" fill={`url(#g${id})`} opacity=".12" />
      <g className="lx-float">
        <rect x="34" y="30" width="70" height="44" rx="9" fill="rgb(var(--c-surface))" stroke="rgb(var(--c-line))" />
        <rect x="44" y="41" width="30" height="5" rx="2.5" fill={`url(#g${id})`} opacity=".9" />
        <rect x="44" y="52" width="48" height="4" rx="2" fill="rgb(var(--c-line))" />
        <rect x="44" y="61" width="38" height="4" rx="2" fill="rgb(var(--c-line))" />
      </g>
      <g className="lx-float lx-delay-2">
        <rect x="84" y="54" width="46" height="34" rx="8" fill="rgb(var(--c-surface))" stroke="rgb(var(--c-line))" />
        <path d="M93 78 l8 -8 l6 5 l10 -11" fill="none" stroke={`url(#g${id})`} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </g>
      <circle cx="126" cy="28" r="4" fill="#bf5af2" opacity=".6" className="lx-float lx-delay-4" />
      <circle cx="30" cy="80" r="3" fill="#0a84ff" opacity=".6" className="lx-float" />
    </svg>
  );
}

export function EmptyState({ icon, title, body, action, compact }: { icon?: ReactNode; title: string; body: string; action?: ReactNode; compact?: boolean }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      className={clsx("card flex flex-col items-center justify-center px-6 text-center", compact ? "py-8" : "py-14")}>
      <div className="relative mb-2">
        <EmptyIllustration className={compact ? "h-16 w-24" : undefined} />
        {icon && <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 rounded-full bg-surface p-2 text-accent shadow-card ring-1 ring-line">{icon}</div>}
      </div>
      <h3 className="mt-3 text-[15px] font-semibold">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </motion.div>
  );
}

export function Logo({ compact }: { compact?: boolean }) {
  const brand = useBrand();
  if (brand?.app_name || brand?.logo_url) {
    return (
      <span className="inline-flex items-center gap-2 text-[17px] font-semibold tracking-tight text-ink">
        {brand.logo_url
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={brand.logo_url} alt="" className="h-7 w-7 rounded-lg object-contain" />
          : <span className="grid h-7 w-7 place-items-center rounded-lg bg-accent text-[13px] font-bold text-white">{(brand.app_name ?? "?").slice(0, 1).toUpperCase()}</span>}
        {!compact && <span className="truncate">{brand.app_name}</span>}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-2 text-[17px] font-semibold tracking-tight text-ink">
      <span className="relative grid h-7 w-7 place-items-center rounded-lg bg-brand text-[13px] font-bold text-white shadow-glow">L</span>
      {!compact && <span>Leadex<span className="text-accent">AI</span></span>}
    </span>
  );
}

/* ------------------------------------------------------------------ extended primitives */
export type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "violet";
const TONES: Record<Tone, string> = {
  neutral: "bg-raised text-neutral-700 ring-line",
  accent: "bg-accent/10 text-accent ring-accent/20",
  success: "bg-success/10 text-success ring-success/20",
  warning: "bg-amber-500/10 text-amber-700 ring-amber-500/20",
  danger: "bg-danger/10 text-danger ring-danger/20",
  violet: "bg-violet-500/10 text-violet-700 ring-violet-500/20",
};
export function Badge({ tone = "neutral", children, className, dot }: { tone?: Tone; children: ReactNode; className?: string; dot?: boolean }) {
  return (
    <span className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset", TONES[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, children, ...p }, ref) {
  return (
    <select ref={ref} {...p} className={clsx(field, "h-10 border-line px-3 text-sm hover:border-muted/40", className)}>
      {children}
    </select>
  );
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & { error?: string }>(
  function Textarea({ className, error, ...p }, ref) {
    return (
      <>
        <textarea ref={ref} {...p} className={clsx(field, "px-4 py-3 text-[15px]", error ? "border-danger" : "border-line hover:border-muted/40", className)} />
        {error && <p className="mt-1 text-xs text-danger">{error}</p>}
      </>
    );
  },
);

function useEscape(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
}

export function Dialog({ open, onClose, title, description, children, footer, wide }: {
  open: boolean; onClose: () => void; title: string; description?: string; children: ReactNode; footer?: ReactNode; wide?: boolean;
}) {
  useEscape(open, onClose);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
          <motion.div role="dialog" aria-modal="true" aria-label={title}
            initial={{ opacity: 0, y: 16, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ type: "spring", damping: 28, stiffness: 380 }}
            className={clsx("relative max-h-[90vh] w-full overflow-y-auto rounded-2xl border border-line bg-surface shadow-lift", wide ? "max-w-2xl" : "max-w-lg")}>
            <div className="flex items-start justify-between gap-4 px-6 pt-6">
              <div>
                <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
                {description && <p className="mt-1 text-sm text-muted">{description}</p>}
              </div>
              <button onClick={onClose} aria-label="Close" className="rounded-full p-1.5 text-muted transition hover:rotate-90 hover:bg-raised focus-ring"><X className="h-4 w-4" /></button>
            </div>
            <div className="px-6 py-5">{children}</div>
            {footer && <div className="flex justify-end gap-2 border-t border-line px-6 py-4">{footer}</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  useEscape(open, onClose);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
          <motion.aside role="dialog" aria-label={title} initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="absolute right-0 top-0 flex h-full w-full max-w-md flex-col border-l border-line bg-surface shadow-lift">
            <div className="flex items-center justify-between border-b border-line px-6 py-4">
              <h2 className="font-semibold">{title}</h2>
              <button onClick={onClose} aria-label="Close" className="rounded-full p-1.5 text-muted transition hover:rotate-90 hover:bg-raised focus-ring"><X className="h-4 w-4" /></button>
            </div>
            <div className="flex-1 overflow-y-auto p-6">{children}</div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function ConfirmDialog({ open, onClose, onConfirm, title, body, confirmLabel = "Confirm", danger, loading }: {
  open: boolean; onClose: () => void; onConfirm: () => void; title: string; body: ReactNode; confirmLabel?: string; danger?: boolean; loading?: boolean;
}) {
  return (
    <Dialog open={open} onClose={onClose} title={title}
      footer={<>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button onClick={onConfirm} loading={loading} className={danger ? "bg-danger hover:bg-danger/90" : undefined}>{confirmLabel}</Button>
      </>}>
      <div className="text-sm text-neutral-700">{body}</div>
    </Dialog>
  );
}

export function Table({ head, children, className }: { head: ReactNode[]; children: ReactNode; className?: string }) {
  return (
    <div className={clsx("card overflow-x-auto", className)}>
      <table className="w-full text-sm">
        <thead className="border-b border-line bg-raised/50 text-left text-xs uppercase tracking-wide text-muted">
          <tr>{head.map((h, i) => <th key={i} className="whitespace-nowrap px-5 py-3 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-line [&>tr]:transition-colors [&>tr:hover]:bg-raised/40">{children}</tbody>
      </table>
    </div>
  );
}

/** Segmented tabs with a shared-layout animated indicator. */
export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: ReactNode }[]; value: T; onChange: (v: T) => void }) {
  const group = useId();
  return (
    <div role="tablist" className="inline-flex max-w-full overflow-x-auto rounded-full bg-raised p-1">
      {tabs.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={clsx("relative whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium transition-colors focus-ring", value === t.id ? "text-ink" : "text-muted hover:text-ink")}>
          {value === t.id && <motion.span layoutId={`tab-${group}`} className="absolute inset-0 rounded-full bg-surface shadow-card" transition={{ type: "spring", damping: 30, stiffness: 400 }} />}
          <span className="relative">{t.label}</span>
        </button>
      ))}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={clsx("shimmer rounded-lg bg-raised", className)} />;
}

export function PageHeader({ title, description, actions, eyebrow }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
        <h1 className="font-display text-[26px] font-semibold tracking-tight sm:text-[30px]">{title}</h1>
        {description && <p className="mt-1 text-[15px] text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ numbers & charts */
/** Counts up from 0 when scrolled into view. Respects prefers-reduced-motion. */
export function AnimatedNumber({ value, format, duration = 1.1 }: { value: number; format?: (n: number) => string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const fmtRef = useRef(format);
  fmtRef.current = format;
  const fmt = useCallback((n: number) => (fmtRef.current ? fmtRef.current(n) : Math.round(n).toLocaleString()), []);
  const prev = useRef(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduce || !inView) { el.textContent = fmt(reduce ? value : prev.current); if (reduce) prev.current = value; return; }
    const c = animate(prev.current, value, { duration, ease: [0.16, 1, 0.3, 1], onUpdate: (v) => { el.textContent = fmt(v); } });
    prev.current = value;
    return () => c.stop();
  }, [value, inView, reduce, duration, fmt]);
  return <span ref={ref} className="tabular-nums">{fmt(0)}</span>;
}

/** Tiny dependency-free sparkline (SVG path with gradient fill + draw-in animation). */
export function Sparkline({ data, className, color = "#0a84ff", height = 36 }: { data: number[]; className?: string; color?: string; height?: number }) {
  const id = useId().replace(/:/g, "");
  const w = 120;
  const max = Math.max(1, ...data);
  const pts = data.map((v, i) => [data.length > 1 ? (i / (data.length - 1)) * w : w / 2, height - 3 - (v / max) * (height - 6)] as const);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = pts.length ? `${line} L${w},${height} L0,${height} Z` : "";
  const flat = data.every((v) => v === 0);
  return (
    <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" className={clsx("h-9 w-full overflow-visible", className)} aria-hidden>
      <defs>
        <linearGradient id={`s${id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".28" /><stop offset="1" stopColor={color} stopOpacity="0" /></linearGradient>
      </defs>
      {!flat && <motion.path d={area} fill={`url(#s${id})`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8, delay: 0.3 }} />}
      <motion.path d={line} fill="none" stroke={color} strokeOpacity={flat ? 0.3 : 1} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.1, ease: "easeOut" }} />
    </svg>
  );
}

export function StatCard({ label, value, icon, hint, tone = "accent", spark, sparkColor, delta, href }: {
  label: string; value: ReactNode; icon?: ReactNode; hint?: ReactNode; tone?: Tone; spark?: number[]; sparkColor?: string;
  delta?: { value: number; label?: string } | null; href?: string;
}) {
  const body = (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }} className="card card-hover relative h-full overflow-hidden p-5">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-muted">{label}</span>
        {icon && <span className={clsx("rounded-xl p-2 ring-1 ring-inset", TONES[tone])}>{icon}</span>}
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="font-display text-[30px] font-semibold tabular-nums tracking-tight">
          {value === undefined || value === null ? <Skeleton className="h-8 w-16" /> : typeof value === "number" ? <AnimatedNumber value={value} /> : value}
        </span>
        {delta && delta.value !== 0 && (
          <span className={clsx("rounded-full px-1.5 py-0.5 text-[11px] font-semibold", delta.value > 0 ? "bg-success/10 text-success" : "bg-danger/10 text-danger")}>
            {delta.value > 0 ? "▲" : "▼"} {Math.abs(delta.value)}{delta.label ?? ""}
          </span>
        )}
      </div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
      {spark && <div className="mt-3 -mb-1"><Sparkline data={spark} color={sparkColor} /></div>}
    </motion.div>
  );
  return href ? <a href={href} className="block rounded-2xl focus-ring">{body}</a> : body;
}

/* ------------------------------------------------------------------ layout helpers */
export function Card({ children, className, title, subtitle, action, icon }: { children: ReactNode; className?: string; title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-40px" }} transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className={clsx("card p-5 sm:p-6", className)}>
      {(title || action) && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div className="min-w-0">
            {title && <h2 className="flex items-center gap-2 text-[15px] font-semibold">{icon}{title}</h2>}
            {subtitle && <p className="mt-0.5 text-[13px] text-muted">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </motion.section>
  );
}

/** Staggered children reveal (use with <Stagger.Item>). */
export function Stagger({ children, className }: { children: ReactNode; className?: string }) {
  return <motion.div className={className} initial="hidden" animate="show" variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06 } } }}>{children}</motion.div>;
}
Stagger.Item = function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return <motion.div className={className} variants={{ hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] } } }}>{children}</motion.div>;
};

export function PageTransition({ children, id }: { children: ReactNode; id: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div key={id} initial={reduce ? false : { opacity: 0, y: 8, filter: "blur(4px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}>
      {children}
    </motion.div>
  );
}

export function Kbd({ children }: { children: ReactNode }) { return <kbd className="kbd">{children}</kbd>; }

export function Progress({ value, className }: { value: number; className?: string }) {
  return (
    <div className={clsx("h-2 overflow-hidden rounded-full bg-raised", className)} role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
      <motion.div className="h-full rounded-full bg-brand" initial={{ width: 0 }} animate={{ width: `${Math.max(0, Math.min(100, value))}%` }} transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }} />
    </div>
  );
}

/* ------------------------------------------------------------------ theme */
type Theme = "light" | "dark";
const ThemeCtx = createContext<{ theme: Theme; toggle: () => void }>({ theme: "light", toggle: () => {} });
function readTheme(): Theme {
  try {
    const t = localStorage.getItem("lx_theme");
    if (t === "dark" || t === "light") return t;
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch { return "light"; }
}
/** Applies the `dark` class to <html> only while the app shell is mounted (marketing pages stay light). */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("light");
  useEffect(() => { setTheme(readTheme()); }, []);
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", theme === "dark");
    return () => root.classList.remove("dark");
  }, [theme]);
  const toggle = useCallback(() => setTheme((t) => {
    const n = t === "dark" ? "light" : "dark";
    try { localStorage.setItem("lx_theme", n); } catch { /* storage unavailable */ }
    return n;
  }), []);
  return <ThemeCtx.Provider value={{ theme, toggle }}>{children}</ThemeCtx.Provider>;
}
export function useTheme() { return useContext(ThemeCtx); }

/* ------------------------------------------------------------------ toasts */
/* <ToastProvider> is mounted in the app shell; call useToast()(message, tone). */
type ToastItem = { id: number; message: string; tone: "success" | "danger" | "neutral" };
const TOAST_MS = 4000;
const ToastCtx = createContext<(message: string, tone?: ToastItem["tone"]) => void>(() => {});
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const dismiss = useCallback((id: number) => setItems((x) => x.filter((t) => t.id !== id)), []);
  const push = useCallback((message: string, tone: ToastItem["tone"] = "neutral") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x.slice(-3), { id, message, tone }]);
    setTimeout(() => dismiss(id), TOAST_MS);
  }, [dismiss]);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-20 right-4 z-[60] flex flex-col gap-2 md:bottom-4">
        <AnimatePresence>
          {items.map((t) => (
            <motion.div key={t.id} layout initial={{ opacity: 0, y: 12, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, x: 24 }}
              className="glass pointer-events-auto relative w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-2xl border border-line shadow-lift">
              <div className="flex items-center gap-2 px-4 py-3 text-sm">
                {t.tone === "success" ? <CheckCircle2 className="h-4 w-4 shrink-0 text-success" /> : t.tone === "danger" ? <AlertCircle className="h-4 w-4 shrink-0 text-danger" /> : <Info className="h-4 w-4 shrink-0 text-accent" />}
                <span className="flex-1 text-ink">{t.message}</span>
                <button onClick={() => dismiss(t.id)} aria-label="Dismiss" className="rounded-full p-1 text-muted hover:bg-raised"><X className="h-3.5 w-3.5" /></button>
              </div>
              <motion.div className={clsx("h-0.5 origin-left", t.tone === "danger" ? "bg-danger" : t.tone === "success" ? "bg-success" : "bg-accent")}
                initial={{ scaleX: 1 }} animate={{ scaleX: 0 }} transition={{ duration: TOAST_MS / 1000, ease: "linear" }} />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}
export function useToast() { return useContext(ToastCtx); }
