"use client";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ArrowLeft, ArrowRight, CalendarDays, CalendarPlus, Check, ChevronLeft, ChevronRight, Clock, Handshake, LifeBuoy, Loader2,
  MessageSquare, Presentation, ShieldCheck,
} from "lucide-react";
import { EASE, Magnetic } from "./motion";
import { serif } from "./fonts";
import { salesApi, PublicError, type Slot, type SlotDay, type SubmitResult } from "./sales-api";

export type FormType = "talk_to_sales" | "demo_request" | "partnership" | "support";
export const TABS: { k: FormType; label: string; icon: typeof MessageSquare; blurb: string }[] = [
  { k: "talk_to_sales", label: "Talk to sales", icon: MessageSquare, blurb: "Plans, pricing, rollout and custom limits." },
  { k: "demo_request", label: "Book a demo", icon: Presentation, blurb: "Pick a time for a live walkthrough." },
  { k: "partnership", label: "Partnerships", icon: Handshake, blurb: "Agencies, resellers and white-label." },
  { k: "support", label: "Support", icon: LifeBuoy, blurb: "Help with your existing workspace." },
];
const INTERESTS: [string, string][] = [
  ["lead_generation", "Lead discovery"], ["crm", "CRM & pipeline"], ["ai_agents", "AI agents"], ["voice_agents", "Voice agents"],
  ["website_studio", "Website Studio"], ["campaigns", "Email campaigns"], ["whatsapp", "WhatsApp"], ["marketplace", "Referral marketplace"],
  ["white_label", "White label"], ["compliance", "Compliance"],
];
const SIZES = ["1", "2-10", "11-50", "51-200", "201-1000", "1000+"];

const schema = z.object({
  name: z.string().trim().min(2, "Please enter your name").max(120),
  email: z.string().trim().email("Enter a valid work email").max(320),
  company: z.string().trim().min(1, "Company is required").max(200),
  role: z.string().trim().max(120).optional().or(z.literal("")),
  team_size: z.string().optional().or(z.literal("")),
  country: z.string().trim().regex(/^([A-Za-z]{2})?$/, "Use a 2-letter country code, e.g. IN").optional(),
  phone: z.string().trim().regex(/^([0-9+()\-. ]{6,40})?$/, "Digits, spaces and + ( ) - only").optional(),
  interests: z.array(z.string()).max(12),
  message: z.string().trim().max(4000, "Please keep it under 4000 characters").optional(),
  preferred_time: z.string().trim().max(120).optional(),
  marketing_consent: z.boolean(),
  privacy_ack: z.literal(true, { errorMap: () => ({ message: "Please acknowledge the privacy notice" }) }),
  website: z.string().max(200).optional(),
});
type Values = z.infer<typeof schema>;
const STEP_FIELDS: (keyof Values)[][] = [["name", "email", "company", "role", "team_size", "country"], ["interests", "message", "phone", "preferred_time"], ["privacy_ack", "marketing_consent"]];

const inputCls = "mt-1.5 h-12 w-full rounded-2xl border border-line bg-white px-4 text-[15px] outline-none transition focus:border-accent focus:ring-4 focus:ring-accent/10";

function F({ label, error, children, hint }: { label: string; error?: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-neutral-800">{label}</span>
      {children}
      {error ? <span role="alert" className="mt-1 block text-xs text-red-600">{error}</span> : hint ? <span className="mt-1 block text-xs text-muted">{hint}</span> : null}
    </label>
  );
}

function Confetti() {
  const reduce = useReducedMotion();
  const bits = useMemo(() => Array.from({ length: 46 }, (_, i) => ({
    x: (Math.random() - 0.5) * 520, y: -(120 + Math.random() * 260), r: Math.random() * 540 - 270,
    c: ["#0a84ff", "#5e5ce6", "#bf5af2", "#d4af37", "#64d2ff", "#30d158"][i % 6], d: Math.random() * 0.25, w: 6 + Math.random() * 6,
  })), []);
  if (reduce) return null;
  return (
    <div aria-hidden className="pointer-events-none absolute left-1/2 top-24 z-10">
      {bits.map((b, i) => (
        <motion.span key={i} className="absolute block rounded-[2px]" style={{ background: b.c, width: b.w, height: b.w * 0.5 }}
          initial={{ x: 0, y: 0, opacity: 1, rotate: 0 }}
          animate={{ x: b.x, y: [0, b.y, b.y + 420], opacity: [1, 1, 0], rotate: b.r }}
          transition={{ duration: 1.9, delay: b.d, ease: "easeOut", times: [0, 0.35, 1] }} />
      ))}
    </div>
  );
}

const NEXT = [
  { t: "Received", b: "Your request is stored securely and our team is notified." },
  { t: "A person reviews it", b: "Someone from Leadex reads it. No automated sales sequence is triggered." },
  { t: "We reply", b: "We aim to reply within 1 business day. That is an aim, not a guarantee." },
];

function Success({ res, type, onReset }: { res: SubmitResult; type: FormType; onReset: () => void }) {
  const when = res.slot_start ? new Date(res.slot_start) : null;
  return (
    <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5, ease: EASE }} className="relative text-center">
      <Confetti />
      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 260, damping: 16, delay: 0.1 }}
        className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-gradient-to-br from-[#0a84ff] to-[#bf5af2] text-white shadow-[0_12px_40px_rgba(94,92,230,0.45)]">
        <Check className="h-8 w-8" />
      </motion.div>
      <h3 className={`${serif.className} mt-6 text-[40px] leading-tight`}>{res.duplicate ? "We already have your request" : type === "demo_request" ? "Your demo is booked" : "Thanks, we're on it"}</h3>
      <p className="mt-2 text-muted">Your reference number</p>
      <p className="mx-auto mt-2 inline-block rounded-2xl border border-line bg-raised px-5 py-2 font-mono text-xl font-semibold tracking-wider">{res.reference}</p>
      {when && (
        <p className="mt-4 text-[15px]"><CalendarDays className="mr-1 inline h-4 w-4 text-accent" />{when.toLocaleString(undefined, { weekday: "long", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" })} <span className="text-muted">(your time)</span></p>
      )}
      {res.ics_url && (
        <a href={salesApi.icsHref(res.ics_url)} className="mt-4 inline-flex h-11 items-center gap-2 rounded-full bg-accent px-5 text-sm font-medium text-white hover:bg-accent-strong">
          <CalendarPlus className="h-4 w-4" /> Add to calendar (.ics)
        </a>
      )}
      <ol className="mx-auto mt-10 max-w-md space-y-0 text-left">
        {NEXT.map((n, i) => (
          <motion.li key={n.t} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.4 + i * 0.15 }} className="relative flex gap-4 pb-6 last:pb-0">
            {i < NEXT.length - 1 && <span className="absolute left-[15px] top-8 h-[calc(100%-24px)] w-px bg-line" />}
            <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-semibold ${i === 0 ? "bg-accent text-white" : "border border-line bg-white text-muted"}`}>{i + 1}</span>
            <div><p className="font-medium">{n.t}</p><p className="text-sm text-muted">{n.b}</p></div>
          </motion.li>
        ))}
      </ol>
      <button onClick={onReset} className="mt-8 text-sm font-medium text-accent">Send another request</button>
    </motion.div>
  );
}

function iso(d: Date) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; }

export function SlotPicker({ value, onChange }: { value: Slot | null; onChange: (s: Slot | null) => void }) {
  const today = useMemo(() => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; }, []);
  const [offset, setOffset] = useState(0);
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => { const d = new Date(today); d.setDate(d.getDate() + offset + i + 1); return d; }), [today, offset]);
  const [day, setDay] = useState<Date>(days[0]);
  const [data, setData] = useState<SlotDay | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setLoading(true); setErr(null);
    salesApi.slots(iso(day)).then(setData).catch((e) => setErr(e.message)).finally(() => setLoading(false));
  }, [day]);
  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">Choose a day</p>
        <div className="flex gap-1">
          <button type="button" aria-label="Previous week" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - 7))} className="grid h-9 w-9 place-items-center rounded-full border border-line disabled:opacity-30"><ChevronLeft className="h-4 w-4" /></button>
          <button type="button" aria-label="Next week" disabled={offset >= 28} onClick={() => setOffset((o) => o + 7)} className="grid h-9 w-9 place-items-center rounded-full border border-line disabled:opacity-30"><ChevronRight className="h-4 w-4" /></button>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-7 gap-1.5">
        {days.map((d) => {
          const on = iso(d) === iso(day);
          return (
            <motion.button type="button" whileTap={{ scale: 0.92 }} key={iso(d)} onClick={() => { setDay(d); onChange(null); }} aria-pressed={on}
              className={`relative rounded-2xl py-2.5 text-center transition-colors ${on ? "text-white" : "border border-line bg-white hover:border-accent/40"}`}>
              {on && <motion.span layoutId="lx-day" className="absolute inset-0 -z-0 rounded-2xl bg-gradient-to-b from-[#0a84ff] to-[#5e5ce6]" />}
              <span className="relative block text-[10px] font-semibold uppercase tracking-wider opacity-70">{d.toLocaleDateString(undefined, { weekday: "short" })}</span>
              <span className="relative block text-lg font-semibold">{d.getDate()}</span>
            </motion.button>
          );
        })}
      </div>
      <p className="mt-5 flex items-center gap-2 text-sm font-medium"><Clock className="h-4 w-4 text-accent" />Available times <span className="font-normal text-muted">shown in your time zone</span></p>
      <div className="mt-3 min-h-[96px]">
        {loading ? <div className="flex h-24 items-center justify-center text-muted"><Loader2 className="h-5 w-5 animate-spin" /></div>
          : err ? <p className="text-sm text-red-600">{err}</p>
          : data && !data.booking_enabled ? <p className="rounded-2xl bg-raised p-4 text-sm text-muted">Online booking is paused. Use “Talk to sales” and we&apos;ll find a time with you.</p>
          : data && data.slots.length === 0 ? <p className="rounded-2xl bg-raised p-4 text-sm text-muted">No free times on this day. Try another day.</p>
          : (
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
              {data?.slots.map((s, i) => {
                const on = value?.start === s.start;
                return (
                  <motion.button type="button" key={s.start} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.025 }}
                    whileTap={{ scale: 0.94 }} onClick={() => onChange(s)} aria-pressed={on}
                    className={`h-11 rounded-xl text-sm font-medium transition-colors ${on ? "bg-accent text-white shadow-[0_6px_20px_rgba(0,113,227,0.35)]" : "border border-line bg-white hover:border-accent hover:text-accent"}`}>
                    {new Date(s.start).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                  </motion.button>
                );
              })}
            </div>
          )}
      </div>
    </div>
  );
}

/** Multi-step inbound form. `compact` renders a single-step quick form (landing page). */
export function ContactForm({ initialType = "talk_to_sales", compact = false, dark = false, lockType = false }: { initialType?: FormType; compact?: boolean; dark?: boolean; lockType?: boolean }) {
  const [type, setType] = useState<FormType>(initialType);
  const [step, setStep] = useState(0);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [res, setRes] = useState<SubmitResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const started = useRef(Date.now());
  const { register, handleSubmit, trigger, watch, setValue, reset, formState: { errors, isSubmitting } } = useForm<Values>({
    resolver: zodResolver(schema), mode: "onTouched",
    defaultValues: { interests: [], marketing_consent: false, privacy_ack: undefined as unknown as true, website: "" },
  });
  useEffect(() => setType(initialType), [initialType]);
  const booking = type === "demo_request" && !compact;
  const steps = compact ? ["Details"] : [...(booking ? ["Time"] : []), "About you", "Your needs", "Send"];
  const formStep = booking ? step - 1 : step;
  const interests = watch("interests");

  async function next() {
    if (booking && step === 0) { if (!slot) { setErr("Please choose a time"); return; } setErr(null); setStep(1); return; }
    const ok = await trigger(STEP_FIELDS[formStep]);
    if (ok) setStep((s) => s + 1);
  }
  const submit = handleSubmit(async (v) => {
    setErr(null);
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const body = {
      type, name: v.name, email: v.email, company: v.company, role: v.role || null, team_size: v.team_size || null,
      country: v.country ? v.country.toUpperCase() : null, phone: v.phone || null, interests: v.interests, message: v.message || null,
      preferred_time: v.preferred_time || null, timezone: tz, marketing_consent: v.marketing_consent, privacy_ack: v.privacy_ack,
      website: v.website || null, form_started_at: started.current,
    };
    try {
      setRes(booking && slot ? await salesApi.book({ ...body, slot_start: slot.start }) : await salesApi.contact(body));
    } catch (e) {
      const pe = e as PublicError;
      if (pe.code === "slot_unavailable") { setSlot(null); setStep(0); }
      setErr(pe.message);
    }
  });
  function restart() { reset(); setRes(null); setStep(0); setSlot(null); started.current = Date.now(); }

  const card = dark ? "border-white/10 bg-white text-neutral-900" : "border-line bg-white";
  if (res) return <div className={`rounded-[32px] border p-6 shadow-lift sm:p-10 ${card}`}><Success res={res} type={type} onReset={restart} /></div>;
  const last = step === steps.length - 1;

  return (
    <form onSubmit={(e) => { e.preventDefault(); if (last) submit(); else next(); }} noValidate className={`relative rounded-[32px] border p-6 shadow-lift sm:p-9 ${card}`}>
      {!compact && !lockType && (
        <div role="tablist" aria-label="Request type" className="-mx-1 mb-7 flex gap-1 overflow-x-auto rounded-2xl bg-raised p-1">
          {TABS.map((t) => (
            <button type="button" role="tab" aria-selected={type === t.k} key={t.k} onClick={() => { setType(t.k); setStep(0); setErr(null); }}
              className={`relative flex shrink-0 items-center gap-2 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-colors ${type === t.k ? "text-neutral-900" : "text-neutral-500 hover:text-neutral-800"}`}>
              {type === t.k && <motion.span layoutId="lx-tab" className="absolute inset-0 rounded-xl bg-white shadow-card" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
              <t.icon className="relative h-4 w-4" /><span className="relative">{t.label}</span>
            </button>
          ))}
        </div>
      )}
      {!compact && (
        <div className="mb-6">
          <div className="flex items-center justify-between text-xs font-medium text-muted"><span>Step {step + 1} of {steps.length} · {steps[step]}</span><span>{TABS.find((t) => t.k === type)?.blurb}</span></div>
          <div className="mt-2 h-1 overflow-hidden rounded-full bg-line"><motion.div animate={{ width: `${((step + 1) / steps.length) * 100}%` }} transition={{ ease: EASE, duration: 0.5 }} className="h-full rounded-full bg-gradient-to-r from-[#0a84ff] via-[#5e5ce6] to-[#bf5af2]" /></div>
        </div>
      )}
      {/* Honeypot: hidden from people and assistive tech; bots tend to fill it. */}
      <div aria-hidden className="absolute -left-[9999px] h-0 w-0 overflow-hidden"><label>Website<input tabIndex={-1} autoComplete="off" {...register("website")} /></label></div>

      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={`${type}-${step}`} initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} transition={{ duration: 0.3, ease: EASE }} className="space-y-4">
          {booking && step === 0 && <SlotPicker value={slot} onChange={(s) => { setSlot(s); setErr(null); }} />}
          {(compact || formStep === 0) && !(booking && step === 0) && (
            <div className="grid gap-4 sm:grid-cols-2">
              <F label="Full name" error={errors.name?.message}><input className={inputCls} autoComplete="name" {...register("name")} /></F>
              <F label="Work email" error={errors.email?.message}><input className={inputCls} type="email" autoComplete="email" {...register("email")} /></F>
              <F label="Company" error={errors.company?.message}><input className={inputCls} autoComplete="organization" {...register("company")} /></F>
              {!compact && <F label="Your role (optional)" error={errors.role?.message}><input className={inputCls} autoComplete="organization-title" {...register("role")} /></F>}
              {!compact && (
                <F label="Team size (optional)">
                  <select className={inputCls} {...register("team_size")}><option value="">Select…</option>{SIZES.map((s) => <option key={s} value={s}>{s}</option>)}</select>
                </F>
              )}
              {!compact && <F label="Country (optional)" error={errors.country?.message} hint="2-letter code, e.g. IN, US, GB"><input className={inputCls} maxLength={2} {...register("country")} /></F>}
              {compact && <F label="Message (optional)" error={errors.message?.message}><input className={inputCls} placeholder="What are you looking to achieve?" {...register("message")} /></F>}
            </div>
          )}
          {!compact && formStep === 1 && (
            <>
              <div>
                <p className="text-sm font-medium">What are you interested in?</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {INTERESTS.map(([k, l]) => {
                    const on = interests.includes(k);
                    return (
                      <motion.button type="button" key={k} whileTap={{ scale: 0.93 }} aria-pressed={on}
                        onClick={() => setValue("interests", on ? interests.filter((x) => x !== k) : [...interests, k])}
                        className={`rounded-full border px-3.5 py-2 text-sm transition-colors ${on ? "border-accent bg-accent/10 font-medium text-accent" : "border-line hover:border-neutral-300"}`}>
                        {on && <Check className="-ml-0.5 mr-1 inline h-3.5 w-3.5" />}{l}
                      </motion.button>
                    );
                  })}
                </div>
              </div>
              <F label={type === "support" ? "Describe the issue" : "Message"} error={errors.message?.message}>
                <textarea rows={4} className={`${inputCls} h-auto py-3`} {...register("message")} placeholder={type === "partnership" ? "Tell us about your agency or partnership idea…" : "Goals, timelines, questions…"} />
              </F>
              <div className="grid gap-4 sm:grid-cols-2">
                <F label="Phone (optional)" error={errors.phone?.message}><input className={inputCls} type="tel" autoComplete="tel" {...register("phone")} /></F>
                <F label="Preferred contact time (optional)" hint={`Your time zone: ${typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : ""}`}><input className={inputCls} placeholder="e.g. weekday mornings" {...register("preferred_time")} /></F>
              </div>
            </>
          )}
          {(compact || formStep === 2) && (
            <div className="space-y-3">
              {!compact && booking && slot && (
                <p className="rounded-2xl bg-raised p-4 text-sm"><CalendarDays className="mr-1.5 inline h-4 w-4 text-accent" />Demo on <b>{new Date(slot.start).toLocaleString(undefined, { weekday: "long", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</b></p>
              )}
              <label className="flex cursor-pointer gap-3 rounded-2xl border border-line p-4 text-sm">
                <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[#0071e3]" {...register("privacy_ack")} />
                <span>I have read the privacy notice: Leadex stores these details to respond to this request and records that I contacted you. <span className="text-muted">Required.</span>
                  {errors.privacy_ack && <span role="alert" className="mt-1 block text-xs text-red-600">{errors.privacy_ack.message}</span>}
                </span>
              </label>
              <label className="flex cursor-pointer gap-3 rounded-2xl border border-line p-4 text-sm">
                <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[#0071e3]" {...register("marketing_consent")} />
                <span>Also send me occasional product news by email. <span className="text-muted">Optional. You can unsubscribe at any time.</span></span>
              </label>
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {err && <p role="alert" className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700">{err}</p>}
      <div className="mt-7 flex items-center justify-between gap-3">
        {step > 0 ? (
          <button type="button" onClick={() => setStep((s) => s - 1)} className="inline-flex h-11 items-center gap-1.5 rounded-full px-4 text-sm font-medium text-neutral-600 hover:bg-raised"><ArrowLeft className="h-4 w-4" />Back</button>
        ) : <span className="flex items-center gap-1.5 text-xs text-muted"><ShieldCheck className="h-4 w-4" />No spam. A person replies.</span>}
        <Magnetic strength={0.2}>
          <button type="submit" disabled={isSubmitting}
            className="inline-flex h-12 items-center gap-2 rounded-full bg-accent px-7 text-[15px] font-medium text-white shadow-[0_8px_24px_rgba(0,113,227,0.35)] transition-colors hover:bg-accent-strong disabled:opacity-60">
            {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {last ? (booking ? "Confirm booking" : "Send request") : "Continue"} {!isSubmitting && <ArrowRight className="h-4 w-4" />}
          </button>
        </Magnetic>
      </div>
      {compact && <p className="mt-4 text-xs text-muted">Want more options? <Link href="/contact" className="text-accent">Open the full form</Link> or <Link href="/demo-booking" className="text-accent">book a demo</Link>.</p>}
    </form>
  );
}
