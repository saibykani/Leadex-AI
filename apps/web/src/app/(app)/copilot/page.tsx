"use client";
import clsx from "clsx";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Suspense, useEffect, useRef, useState } from "react";
import { ArrowUp, Database, ExternalLink, Lock, ShieldCheck, Sparkles, User } from "lucide-react";
import { growth, fmtMoney, type CopilotAnswer, type CopilotRow } from "@/lib/growth";
import { useSession } from "@/lib/session-context";
import { Badge, EmptyState, PageHeader } from "@/components/ui";

type Msg = { id: number; role: "user" | "assistant"; text: string; data?: CopilotAnswer; error?: boolean };
const FALLBACK = ["How many leads do I have?", "Show hot leads with high interest", "Which leads have a budget over 50k?", "What is my pipeline value?", "What is my conversion rate?", "Businesses without a website"];

export default function CopilotPage() {
  return <Suspense><Copilot /></Suspense>;
}

function Copilot() {
  const { can, current } = useSession();
  const params = useSearchParams();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [chips, setChips] = useState<string[]>(FALLBACK);
  const endRef = useRef<HTMLDivElement>(null);
  const asked = useRef(false);

  useEffect(() => { growth.suggestions().then((s) => setChips(s.suggestions)).catch(() => {}); }, [current.organization.id]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, busy]);

  const ask = async (question: string) => {
    const text = question.trim();
    if (!text || busy) return;
    setQ("");
    setMsgs((m) => [...m, { id: Date.now(), role: "user", text }]);
    setBusy(true);
    try {
      const r = await growth.ask(text);
      setMsgs((m) => [...m, { id: Date.now() + 1, role: "assistant", text: r.answer, data: r }]);
    } catch (e) {
      setMsgs((m) => [...m, { id: Date.now() + 1, role: "assistant", text: (e as Error).message, error: true }]);
    } finally { setBusy(false); }
  };
  useEffect(() => {
    const initial = params.get("q");
    if (initial && !asked.current) { asked.current = true; void ask(initial); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  if (!can("leads:read")) return <EmptyState icon={<Lock className="h-5 w-5" />} title="No access" body="Copilot answers questions about leads; your role doesn't include lead access." />;

  return (
    <div className="mx-auto flex max-w-3xl flex-col">
      <PageHeader eyebrow="AI Copilot" title={<>Ask your <span className="text-gradient">pipeline</span></>}
        description="Plain-English questions, answered from your live workspace data — with every source cited."
        actions={<Badge tone="success" dot><ShieldCheck className="h-3 w-3" />Read-only</Badge>} />

      <div className="mt-6 flex-1 space-y-5">
        {msgs.length === 0 && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="ring-gradient relative overflow-hidden rounded-3xl border border-line bg-surface p-6 text-center shadow-card sm:p-10">
            <div aria-hidden className="lx-blob absolute -top-20 left-1/2 h-56 w-56 -translate-x-1/2 rounded-full bg-[#5e5ce6]/15 blur-3xl" />
            <div className="relative mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-brand text-white shadow-glow"><Sparkles className="h-6 w-6" /></div>
            <h2 className="relative mt-4 text-lg font-semibold">What would you like to know?</h2>
            <p className="relative mx-auto mt-1 max-w-md text-sm text-muted">I run safe, tenant-scoped queries over leads, businesses, outcomes, campaigns and websites. I never create, change or send anything.</p>
            <div className="relative mt-6 flex flex-wrap justify-center gap-2">
              {chips.map((c, i) => (
                <motion.button key={c} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + i * 0.04 }} onClick={() => ask(c)}
                  className="rounded-full border border-line bg-surface px-3.5 py-1.5 text-[13px] text-neutral-700 transition hover:-translate-y-0.5 hover:border-accent/40 hover:text-accent hover:shadow-card active:scale-95">
                  {c}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
        <AnimatePresence initial={false}>
          {msgs.map((m) => <Message key={m.id} m={m} />)}
        </AnimatePresence>
        {busy && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-3">
            <Avatar assistant />
            <div className="flex gap-1 rounded-2xl bg-raised px-4 py-3">{[0, 1, 2].map((i) => <motion.span key={i} className="h-2 w-2 rounded-full bg-accent" animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }} transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.15 }} />)}</div>
          </motion.div>
        )}
        <div ref={endRef} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); void ask(q); }} className="sticky bottom-20 mt-6 md:bottom-4">
        {msgs.length > 0 && (
          <div className="mb-2 flex gap-2 overflow-x-auto pb-1">
            {chips.slice(0, 5).map((c) => <button type="button" key={c} onClick={() => ask(c)} className="glass shrink-0 rounded-full border border-line px-3 py-1 text-xs text-muted transition hover:text-accent">{c}</button>)}
          </div>
        )}
        <div className="glass flex items-center gap-2 rounded-2xl border border-line p-2 shadow-lift focus-within:border-accent/50 focus-within:ring-4 focus-within:ring-accent/10">
          <Sparkles className="ml-2 h-5 w-5 shrink-0 text-accent" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Which qualified leads in Pune have a budget over 50k?" aria-label="Ask a question" maxLength={500}
            className="h-11 min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-muted" />
          <button type="submit" disabled={!q.trim() || busy} aria-label="Send"
            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand text-white shadow-glow transition hover:brightness-110 active:scale-95 disabled:opacity-40 disabled:shadow-none">
            <ArrowUp className="h-5 w-5" />
          </button>
        </div>
      </form>
    </div>
  );
}

function Avatar({ assistant }: { assistant?: boolean }) {
  return assistant
    ? <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-brand text-white shadow-glow"><Sparkles className="h-4 w-4" /></span>
    : <span className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-raised text-muted ring-1 ring-line"><User className="h-4 w-4" /></span>;
}

/** Word-by-word reveal for a streaming feel (content is already final and fully computed server-side). */
function Reveal({ text }: { text: string }) {
  const reduce = useReducedMotion();
  const words = text.split(/(\s+)/);
  if (reduce) return <>{text}</>;
  return <>{words.map((w, i) => <motion.span key={i} initial={{ opacity: 0, filter: "blur(4px)" }} animate={{ opacity: 1, filter: "blur(0px)" }} transition={{ delay: i * 0.018, duration: 0.25 }}>{w}</motion.span>)}</>;
}

function cell(r: CopilotRow) {
  if (typeof r.budget_mid === "number" && typeof r.currency === "string") return fmtMoney(r.budget_mid, r.currency);
  if (r.value && typeof r.value === "object") return Object.entries(r.value as Record<string, number>).map(([c, v]) => fmtMoney(v, c)).join(", ") || "—";
  if (typeof r.count === "number") return String(r.count);
  return [r.status, r.city, r.interest].filter((x) => typeof x === "string" && x).join(" · ").replace(/_/g, " ");
}

function Message({ m }: { m: Msg }) {
  if (m.role === "user") {
    return (
      <motion.div layout initial={{ opacity: 0, y: 8, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} className="flex justify-end gap-3">
        <div className="max-w-[85%] rounded-2xl rounded-tr-md bg-accent px-4 py-2.5 text-[15px] text-white shadow-sm">{m.text}</div>
        <Avatar />
      </motion.div>
    );
  }
  const d = m.data;
  return (
    <motion.div layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3">
      <Avatar assistant />
      <div className="min-w-0 flex-1">
        <div className={clsx("rounded-2xl rounded-tl-md border px-4 py-3 text-[15px] leading-relaxed", m.error ? "border-danger/30 bg-danger/5 text-danger" : d?.refused ? "border-amber-200 bg-amber-50 text-amber-800" : "border-line bg-surface shadow-card")}>
          <Reveal text={m.text} />
          {d && d.rows.length > 0 && (
            <motion.ul initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mt-3 divide-y divide-line overflow-hidden rounded-xl border border-line">
              {d.rows.slice(0, 10).map((r, i) => (
                <motion.li key={`${r.type}-${r.id}`} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.35 + i * 0.04 }}>
                  {r.href ? (
                    <Link href={r.href} className="group flex items-center justify-between gap-3 px-3 py-2 text-sm transition hover:bg-raised/60">
                      <span className="truncate font-medium">{r.label}</span>
                      <span className="flex shrink-0 items-center gap-2 text-xs capitalize text-muted">{cell(r)}<ExternalLink className="h-3 w-3 opacity-0 transition group-hover:opacity-100" /></span>
                    </Link>
                  ) : (
                    <div className="flex items-center justify-between gap-3 px-3 py-2 text-sm"><span className="truncate capitalize">{r.label}</span><span className="text-xs text-muted">{cell(r)}</span></div>
                  )}
                </motion.li>
              ))}
            </motion.ul>
          )}
        </div>
        {d && (
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 px-1 text-[11px] text-muted">
            {d.tool && <span className="flex items-center gap-1"><Database className="h-3 w-3" />{d.tool}({Object.entries(d.args).filter(([, v]) => v !== null && v !== undefined).map(([k, v]) => `${k}=${v}`).join(", ")})</span>}
            <span>{d.mode === "ollama" ? `routed by ${d.model}` : d.mode === "guardrail" ? "guardrail" : "rule-based routing"}</span>
            {d.citations.map((c) => <Link key={c.href} href={c.href} className="text-accent hover:underline">{c.label} →</Link>)}
          </div>
        )}
      </div>
    </motion.div>
  );
}
