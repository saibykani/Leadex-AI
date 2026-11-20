"use client";
import Link from "next/link";
import { Fragment, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowRight, Calculator, Check, ChevronDown, Minus, Sparkles } from "lucide-react";
import { CTA, EASE, Mesh, Reveal, SectionHead, Tilt, WordReveal } from "./motion";
import { serif } from "./fonts";
import { fmtLimit, LIMIT_LABEL, money, salesApi, type PublicPlan } from "./sales-api";

type Cycle = "monthly" | "annual";

function Toggle({ cycle, set }: { cycle: Cycle; set: (c: Cycle) => void }) {
  return (
    <div role="radiogroup" aria-label="Billing period" className="relative inline-flex rounded-full border border-line bg-white p-1 shadow-card">
      {(["monthly", "annual"] as Cycle[]).map((c) => (
        <button key={c} role="radio" aria-checked={cycle === c} onClick={() => set(c)}
          className={`relative z-[1] h-10 rounded-full px-5 text-sm font-medium transition-colors ${cycle === c ? "text-white" : "text-neutral-600 hover:text-neutral-900"}`}>
          {cycle === c && <motion.span layoutId="lx-cycle" className="absolute inset-0 -z-[1] rounded-full bg-gradient-to-r from-[#0a84ff] to-[#5e5ce6]" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
          {c === "monthly" ? "Monthly" : "Annual"}
        </button>
      ))}
    </div>
  );
}

function Price({ p, cycle }: { p: PublicPlan; cycle: Cycle }) {
  const v = cycle === "annual" ? (p.price_annual ?? null) : p.price_monthly;
  const show = v !== null && !p.contact_sales;
  return (
    <div className="mt-6 h-[60px]">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={`${cycle}-${v}`} initial={{ opacity: 0, y: 14, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          exit={{ opacity: 0, y: -14, filter: "blur(6px)" }} transition={{ duration: 0.35, ease: EASE }}>
          {show ? (
            <p className="flex items-baseline gap-1.5">
              <span className="text-[44px] font-semibold leading-none tracking-[-0.03em]">{money(v!, p.currency)}</span>
              <span className="text-sm text-muted">/ month{cycle === "annual" ? ", billed annually" : ""}</span>
            </p>
          ) : (
            <p className={`${serif.className} text-[38px] leading-none`}>{p.contact_sales ? "Let's talk" : "Contact sales"}</p>
          )}
        </motion.div>
      </AnimatePresence>
      {!show && cycle === "annual" && p.price_monthly && !p.price_annual && !p.contact_sales && <p className="mt-1 text-xs text-muted">Annual price on request</p>}
    </div>
  );
}

const KEY_LIMITS = ["users", "leads", "searches", "voice_minutes", "websites", "agents"];

function PlanCard({ p, cycle }: { p: PublicPlan; cycle: Cycle }) {
  const priced = (cycle === "annual" ? p.price_annual : p.price_monthly) !== null && !p.contact_sales;
  return (
    <Tilt className="h-full rounded-[28px]" max={5}>
      <div className={`relative flex h-full flex-col rounded-[28px] p-[1.5px] ${p.highlight ? "bg-gradient-to-b from-[#0a84ff] via-[#5e5ce6] to-[#bf5af2] shadow-[0_30px_80px_-30px_rgba(94,92,230,0.55)]" : "bg-line"}`}>
        <div className="flex h-full flex-col rounded-[27px] bg-white p-7">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-xl font-semibold tracking-tight">{p.name}</h3>
            {(p.badge || p.highlight) && (
              <span className="rounded-full bg-gradient-to-r from-[#0a84ff] to-[#bf5af2] px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-white">{p.badge ?? "Recommended"}</span>
            )}
          </div>
          <p className="mt-1 min-h-[20px] text-sm text-muted">{p.tagline ?? ""}</p>
          <Price p={p} cycle={cycle} />
          <ul className="mt-6 space-y-2.5 text-[14.5px]">
            {KEY_LIMITS.map((k) => (
              <li key={k} className="flex items-center justify-between gap-3 border-b border-line/60 pb-2.5 last:border-0">
                <span className="text-muted">{LIMIT_LABEL[k]}</span><span className="font-medium tabular-nums">{fmtLimit(k, p.limits[k])}</span>
              </li>
            ))}
          </ul>
          {p.bullets.length > 0 && (
            <ul className="mt-5 flex-1 space-y-2 text-[14.5px]">
              {p.bullets.map((b) => <li key={b} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-accent" />{b}</li>)}
            </ul>
          )}
          <div className="flex-1" />
          <motion.div whileTap={{ scale: 0.96 }} className="mt-7">
            <Link href={priced ? "/register" : `/contact?type=talk_to_sales&plan=${p.code}`}
              className={`flex h-11 items-center justify-center gap-1.5 rounded-full text-[15px] font-medium transition-colors ${p.highlight ? "bg-accent text-white hover:bg-accent-strong" : "border border-line hover:bg-raised"}`}>
              {priced ? "Start free trial" : "Talk to sales"} <ArrowRight className="h-4 w-4" />
            </Link>
          </motion.div>
        </div>
      </div>
    </Tilt>
  );
}

const GROUPS: { title: string; rows: string[] }[] = [
  { title: "Team & CRM", rows: ["users", "leads"] },
  { title: "Discovery & AI", rows: ["searches", "ai_tokens", "agents", "voice_minutes"] },
  { title: "Outreach & web", rows: ["email_accounts", "websites", "workflows"] },
  { title: "Platform", rows: ["storage_mb"] },
];
const INCLUDED = ["Tenant isolation (database row-level security)", "Consent-gated outreach & suppression lists", "Audit log", "Open-source AI by default"];

function Comparison({ plans }: { plans: PublicPlan[] }) {
  const [open, setOpen] = useState<Record<string, boolean>>({ "Team & CRM": true, "Discovery & AI": true, "Outreach & web": true, Platform: true, Included: true });
  return (
    <div className="mx-auto mt-14 max-w-6xl overflow-x-auto rounded-3xl border border-line bg-white shadow-card">
      <table className="w-full min-w-[760px] border-collapse text-left text-[14px]">
        <thead className="sticky top-14 z-[3]">
          <tr className="bg-white/90 backdrop-blur">
            <th className="w-[26%] p-4 text-sm font-semibold">Compare plans</th>
            {plans.map((p) => (
              <th key={p.code} className={`p-4 text-center text-sm font-semibold ${p.highlight ? "text-accent" : ""}`}>{p.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {[...GROUPS, { title: "Included", rows: [] as string[] }].map((g) => (
            <Fragment key={g.title}>
              <tr className="border-t border-line bg-raised/60">
                <td colSpan={plans.length + 1} className="p-0">
                  <button onClick={() => setOpen((o) => ({ ...o, [g.title]: !o[g.title] }))} aria-expanded={open[g.title]}
                    className="flex w-full items-center gap-2 px-4 py-3 text-[13px] font-semibold uppercase tracking-wider text-neutral-600">
                    <motion.span animate={{ rotate: open[g.title] ? 0 : -90 }}><ChevronDown className="h-4 w-4" /></motion.span>{g.title}
                  </button>
                </td>
              </tr>
              {open[g.title] && (g.title === "Included" ? INCLUDED.map((t) => (
                <tr key={t} className="border-t border-line/60">
                  <td className="p-4 text-muted">{t}</td>
                  {plans.map((p) => <td key={p.code} className="p-4 text-center"><Check className="mx-auto h-4 w-4 text-accent" /></td>)}
                </tr>
              )) : g.rows.map((k) => (
                <tr key={k} className="border-t border-line/60">
                  <td className="p-4 text-muted">{LIMIT_LABEL[k]}</td>
                  {plans.map((p) => (
                    <td key={p.code} className={`p-4 text-center font-medium tabular-nums ${p.highlight ? "bg-[#f4f7ff]" : ""}`}>
                      {p.limits[k] === 0 ? <Minus className="mx-auto h-4 w-4 text-neutral-300" /> : fmtLimit(k, p.limits[k])}
                    </td>
                  ))}
                </tr>
              )))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Field({ label, value, set, step = 1, prefix, suffix }: { label: string; value: number; set: (n: number) => void; step?: number; prefix?: string; suffix?: string }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-white/80">{label}</span>
      <div className="mt-2 flex h-12 items-center rounded-2xl border border-white/15 bg-white/[0.06] px-4 focus-within:border-[#64d2ff]">
        {prefix && <span className="mr-1 text-white/50">{prefix}</span>}
        <input type="number" inputMode="decimal" min={0} step={step} value={Number.isFinite(value) ? value : 0}
          onChange={(e) => set(Math.max(0, Number(e.target.value)))} className="w-full bg-transparent text-lg font-medium text-white outline-none" />
        {suffix && <span className="ml-1 text-white/50">{suffix}</span>}
      </div>
    </label>
  );
}

function Roi() {
  const [leads, setLeads] = useState(200);
  const [rate, setRate] = useState(3);
  const [deal, setDeal] = useState(1500);
  const deals = (leads * rate) / 100;
  const revenue = deals * deal;
  return (
    <section className="relative overflow-hidden bg-[#05060f] px-4 py-24 text-white sm:px-6">
      <Mesh dark />
      <div className="relative mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
        <div>
          <p className="inline-flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.2em] text-[#f5e6b8]"><Calculator className="h-4 w-4" /> Revenue estimator</p>
          <h2 className={`${serif.className} mt-4 text-[44px] leading-[1.02] sm:text-[60px]`}>What could your pipeline be worth?</h2>
          <p className="mt-5 max-w-lg text-lg text-white/65">A simple, transparent calculation from your own numbers. It is an estimate only, not a promise of results: Leadex does not guarantee leads, close rates or revenue.</p>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <Field label="Leads / month" value={leads} set={setLeads} />
            <Field label="Close rate" value={rate} set={setRate} step={0.5} suffix="%" />
            <Field label="Avg. deal value" value={deal} set={setDeal} step={50} prefix="$" />
          </div>
        </div>
        <Tilt className="rounded-[32px]" max={6}>
          <div className="rounded-[32px] border border-white/10 bg-white/[0.04] p-8 backdrop-blur sm:p-10">
            <span className="rounded-full border border-[#d4af37]/40 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-[#f5e6b8]">Estimate</span>
            <p className="mt-6 text-sm text-white/60">Estimated new revenue / month</p>
            <motion.p key={Math.round(revenue)} initial={{ opacity: 0.4, y: 6 }} animate={{ opacity: 1, y: 0 }}
              className="mt-1 bg-gradient-to-r from-[#64d2ff] via-[#a5a3ff] to-[#f5e6b8] bg-clip-text text-[52px] font-semibold tracking-[-0.03em] text-transparent sm:text-[64px]">
              {money(Math.round(revenue), "USD")}
            </motion.p>
            <p className="mt-2 text-white/60">≈ {deals.toLocaleString(undefined, { maximumFractionDigits: 1 })} closed deals / month</p>
            <div className="mt-8 rounded-2xl border border-white/10 bg-black/30 p-4 font-mono text-[13px] leading-relaxed text-white/75">
              revenue = leads × close rate × deal value<br />
              = {leads.toLocaleString()} × {rate}% × ${deal.toLocaleString()}
            </div>
          </div>
        </Tilt>
      </div>
    </section>
  );
}

const FAQ = [
  { q: "Why do some plans say “Contact sales”?", a: "We only publish a price once it is final. Until then, talk to us and we will give you a written quote. We never show placeholder prices." },
  { q: "Can I cancel anytime?", a: "Yes. Plans can be changed or cancelled from Billing inside your workspace. Cancellation takes effect at the end of the current billing period." },
  { q: "Is there a free trial?", a: "Yes. Every new workspace starts on a free trial with real (smaller) limits so you can try each module before choosing a plan." },
  { q: "How is my data kept separate from other customers?", a: "Every organization's data is isolated at the database level using PostgreSQL row-level security, and every sensitive action is written to an audit log." },
  { q: "Will Leadex contact people without consent?", a: "No. Outreach is gated: the platform checks recorded consent, suppression lists, kill switches and country-specific calling windows before anything is sent or dialled." },
  { q: "Which AI models do you use?", a: "Open-source models by default, which you can self-host (for example via Ollama). Paid model providers are optional and only used if you enable them." },
  { q: "What happens if I hit a plan limit?", a: "You see a clear notice in the app and can upgrade, or wait for the next period. Limits are enforced by the product, not by surprise overage bills." },
];

function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section className="px-4 py-24 sm:px-6">
      <SectionHead eyebrow="FAQ" title="Questions, answered honestly." />
      <div className="mx-auto mt-12 max-w-3xl divide-y divide-line rounded-3xl border border-line bg-white shadow-card">
        {FAQ.map((f, i) => (
          <div key={f.q}>
            <button onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}
              className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left text-[16px] font-medium">
              {f.q}
              <motion.span animate={{ rotate: open === i ? 45 : 0 }} className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-raised text-lg leading-none">+</motion.span>
            </button>
            <AnimatePresence initial={false}>
              {open === i && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3, ease: EASE }} className="overflow-hidden">
                  <p className="px-6 pb-6 text-[15px] leading-relaxed text-muted">{f.a}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        ))}
      </div>
    </section>
  );
}

export function PricingView() {
  const [plans, setPlans] = useState<PublicPlan[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [cycle, setCycle] = useState<Cycle>("monthly");
  const reduce = useReducedMotion();
  useEffect(() => { salesApi.pricing().then((r) => setPlans(r.plans)).catch((e) => setErr(e.message)); }, []);
  const anyPrice = useMemo(() => plans?.some((p) => p.price_monthly || p.price_annual), [plans]);
  return (
    <>
      <section className="relative overflow-hidden px-4 pb-16 pt-32 text-center sm:px-6 sm:pt-40">
        <Mesh />
        <div className="relative mx-auto max-w-4xl">
          <motion.p initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="inline-flex items-center gap-2 rounded-full border border-line bg-white/80 px-4 py-1.5 text-sm shadow-sm backdrop-blur">
            <Sparkles className="h-4 w-4 text-accent" /> Pricing
          </motion.p>
          <h1 className={`${serif.className} mt-6 text-[52px] leading-[0.98] tracking-[-0.01em] sm:text-[88px]`}>
            <WordReveal text="Plans that scale" /> <span className="block bg-gradient-to-r from-[#0a84ff] via-[#5e5ce6] to-[#bf5af2] bg-clip-text italic text-transparent">with your ambition.</span>
          </h1>
          <Reveal i={2}><p className="mx-auto mt-6 max-w-2xl text-lg text-muted">Every plan includes the full compliance layer, data isolation and open-source AI. Limits below are the real limits the product enforces.</p></Reveal>
          <Reveal i={3} className="mt-9 flex flex-col items-center gap-3">
            <Toggle cycle={cycle} set={setCycle} />
            {!anyPrice && plans && <p className="text-xs text-muted">Prices are being finalised. Talk to sales for a quote.</p>}
          </Reveal>
        </div>
      </section>
      <section className="px-4 pb-10 sm:px-6">
        {err && <p className="mx-auto max-w-xl rounded-2xl border border-line bg-raised p-5 text-center text-muted">Pricing could not be loaded right now. <Link className="font-medium text-accent" href="/contact">Talk to sales</Link> for a quote.</p>}
        {!plans && !err && (
          <div className="mx-auto grid max-w-6xl gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => <div key={i} className="h-[520px] animate-pulse rounded-[28px] bg-raised" />)}
          </div>
        )}
        {plans && (
          <div className="mx-auto grid max-w-6xl gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {plans.map((p, i) => <Reveal key={p.code} i={i % 3}><PlanCard p={p} cycle={cycle} /></Reveal>)}
          </div>
        )}
        <p className="mx-auto mt-6 max-w-3xl text-center text-xs text-muted">Taxes may apply. Annual prices are shown per month. Need higher limits or a custom agreement? <Link href="/contact" className="text-accent">Talk to sales</Link>.</p>
      </section>
      {plans && (
        <section className="px-4 py-16 sm:px-6">
          <SectionHead eyebrow="Compare" title="Every limit, side by side." />
          <Comparison plans={plans} />
        </section>
      )}
      <Roi />
      <Faq />
      <section className="px-4 pb-24 sm:px-6">
        <Reveal className="relative mx-auto max-w-5xl overflow-hidden rounded-[36px] bg-[#05060f] px-6 py-16 text-center text-white">
          <Mesh dark />
          <h2 className={`${serif.className} relative text-[40px] leading-tight sm:text-[56px]`}>Not sure which plan fits?</h2>
          <p className="relative mx-auto mt-3 max-w-xl text-white/70">Tell us about your team and goals. A person, not a bot, will reply.</p>
          <div className="relative mt-8 flex flex-wrap justify-center gap-3">
            <CTA href="/contact?type=talk_to_sales" variant="white">Talk to sales <ArrowRight className="h-4 w-4" /></CTA>
            <CTA href="/register" variant="ghost">Start free trial</CTA>
          </div>
        </Reveal>
      </section>
    </>
  );
}
