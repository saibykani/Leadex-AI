"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Building2, CalendarClock, Lock, Mail, ShieldCheck, Sparkles, Users } from "lucide-react";
import { Mesh, Reveal, Tilt, WordReveal } from "./motion";
import { serif } from "./fonts";
import { ContactForm, TABS, type FormType } from "./contact";

const POINTS = [
  { icon: Users, t: "Talk to a person", b: "Your message goes to the Leadex team, not into an automated drip sequence." },
  { icon: CalendarClock, t: "Response aim", b: "We aim to reply within 1 business day. It's an aim, not a guarantee." },
  { icon: ShieldCheck, t: "Consent respected", b: "We use your details only to respond, unless you separately opt in to product news." },
  { icon: Lock, t: "Stored securely", b: "Requests are stored in our own isolated workspace with an audit trail." },
];

function Hero({ title, accent, body, eyebrow }: { title: string; accent: string; body: string; eyebrow: string }) {
  const reduce = useReducedMotion();
  return (
    <section className="relative overflow-hidden px-4 pb-10 pt-32 sm:px-6 sm:pt-40">
      <Mesh />
      <div className="relative mx-auto max-w-4xl text-center">
        <motion.p initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="inline-flex items-center gap-2 rounded-full border border-line bg-white/80 px-4 py-1.5 text-sm shadow-sm backdrop-blur">
          <Sparkles className="h-4 w-4 text-accent" /> {eyebrow}
        </motion.p>
        <h1 className={`${serif.className} mt-6 text-[50px] leading-[0.98] sm:text-[84px]`}>
          <WordReveal text={title} /> <span className="block bg-gradient-to-r from-[#0a84ff] via-[#5e5ce6] to-[#bf5af2] bg-clip-text italic text-transparent">{accent}</span>
        </h1>
        <Reveal i={2}><p className="mx-auto mt-6 max-w-2xl text-lg text-muted">{body}</p></Reveal>
      </div>
    </section>
  );
}

function Side() {
  return (
    <div className="space-y-4">
      {POINTS.map(({ icon: Icon, t, b }, i) => (
        <Reveal key={t} i={i}>
          <motion.div whileHover={{ x: 6 }} className="flex gap-4 rounded-3xl border border-line bg-white/80 p-5 shadow-card backdrop-blur">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-[#0a84ff] to-[#5e5ce6] text-white"><Icon className="h-5 w-5" /></span>
            <div><p className="font-semibold">{t}</p><p className="mt-0.5 text-[15px] text-muted">{b}</p></div>
          </motion.div>
        </Reveal>
      ))}
      <Reveal i={4}>
        <Tilt className="rounded-3xl" max={5}>
          <div className="relative overflow-hidden rounded-3xl bg-[#05060f] p-6 text-white">
            <div aria-hidden className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-[#d4af37]/20 blur-3xl" />
            <Building2 className="h-5 w-5 text-[#f5e6b8]" />
            <p className="mt-3 font-semibold">Already a customer?</p>
            <p className="mt-1 text-sm text-white/65">Sign in and use the Support tab, or check Billing for plan changes.</p>
            <Link href="/login" className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-[#f5e6b8]"><Mail className="h-4 w-4" /> Sign in</Link>
          </div>
        </Tilt>
      </Reveal>
    </div>
  );
}

export function ConnectView() {
  const [type, setType] = useState<FormType>("talk_to_sales");
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("type");
    if (t && TABS.some((x) => x.k === t)) setType(t as FormType);
  }, []);
  return (
    <>
      <Hero eyebrow="Connect with the team" title="Let's build your" accent="growth engine." body="Talk to sales, book a live demo, explore a partnership or get support. Pick what fits and we'll take it from there." />
      <section className="px-4 pb-28 sm:px-6">
        <div className="mx-auto grid max-w-6xl items-start gap-8 lg:grid-cols-[1.45fr_1fr]">
          <Reveal><ContactForm initialType={type} /></Reveal>
          <Side />
        </div>
      </section>
    </>
  );
}

export function DemoBookingView() {
  return (
    <>
      <Hero eyebrow="Book a demo" title="See Leadex" accent="in thirty minutes." body="Choose a time that suits you. You'll get a reference number and a calendar file instantly; we'll email the meeting link before the call." />
      <section className="px-4 pb-28 sm:px-6">
        <div className="mx-auto grid max-w-6xl items-start gap-8 lg:grid-cols-[1.45fr_1fr]">
          <Reveal><ContactForm initialType="demo_request" lockType /></Reveal>
          <Side />
        </div>
        <p className="mx-auto mt-8 max-w-2xl text-center text-xs text-muted">Bookings are confirmed in Leadex directly. Google Calendar and Microsoft 365 sync is planned, not yet available.</p>
      </section>
    </>
  );
}
