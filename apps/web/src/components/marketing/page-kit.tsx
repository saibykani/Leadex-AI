"use client";
import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { ArrowRight, type LucideIcon } from "lucide-react";
import { CTA, Mesh, Parallax, Reveal, Tilt, WordReveal } from "./motion";
import { BrowserMock, ChatBubbles, Funnel, GlobeMap, NetworkGraph, Waveform } from "./illustrations";

const VISUALS = {
  globe: () => <GlobeMap className="w-full" />,
  wave: () => (
    <div className="rounded-3xl border border-line bg-white p-6 shadow-lift">
      <Waveform bars={30} className="h-24" />
      <div className="mt-6"><ChatBubbles /></div>
    </div>
  ),
  browser: () => <BrowserMock title="your-business.preview" />,
  network: () => <NetworkGraph className="w-full" />,
  funnel: () => <div className="rounded-3xl border border-line bg-white p-6 shadow-lift"><Funnel /></div>,
};
export type VisualKey = keyof typeof VISUALS;

export function PageHero({ eyebrow, title, body, visual }: { eyebrow: string; title: string; body: string; visual?: VisualKey }) {
  const V = visual ? VISUALS[visual] : null;
  return (
    <section className="relative overflow-hidden px-4 pb-20 pt-28 sm:px-6 sm:pt-36">
      <Mesh />
      <div className={`relative mx-auto grid max-w-6xl items-center gap-12 ${V ? "lg:grid-cols-2" : "text-center"}`}>
        <div>
          <motion.p initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="text-[15px] font-semibold text-accent">{eyebrow}</motion.p>
          <h1 className="mt-3 text-[40px] font-semibold leading-[1.04] tracking-[-0.03em] sm:text-[64px]"><WordReveal text={title} /></h1>
          <motion.p initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
            className={`mt-6 max-w-2xl text-lg leading-relaxed text-muted sm:text-xl ${V ? "" : "mx-auto"}`}>{body}</motion.p>
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.45 }}
            className={`mt-9 flex flex-wrap gap-3 ${V ? "" : "justify-center"}`}>
            <CTA href="/register">Start free <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" /></CTA>
            <CTA href="/pricing" variant="ghost">See plans</CTA>
          </motion.div>
        </div>
        {V && (
          <motion.div initial={{ opacity: 0, scale: 0.92, y: 30 }} animate={{ opacity: 1, scale: 1, y: 0 }} transition={{ duration: 1, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}>
            <Parallax speed={30}><Tilt className="mx-auto max-w-md rounded-3xl" max={7}><V /></Tilt></Parallax>
          </motion.div>
        )}
      </div>
    </section>
  );
}

export type Feature = { icon: LucideIcon; title: string; body: string };

export function FeatureGrid({ title, items, eyebrow }: { title: string; eyebrow?: string; items: Feature[] }) {
  return (
    <section className="px-4 py-20 sm:px-6">
      <div className="mx-auto max-w-6xl">
        {eyebrow && <Reveal><p className="text-[15px] font-semibold text-accent">{eyebrow}</p></Reveal>}
        <h2 className="mt-2 max-w-3xl text-[30px] font-semibold leading-tight tracking-[-0.02em] sm:text-[44px]"><WordReveal text={title} /></h2>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map(({ icon: Icon, title: t, body }, i) => (
            <Reveal key={t} i={i % 3}>
              <Tilt className="h-full rounded-3xl" max={6}>
                <div className="group h-full rounded-3xl border border-line bg-white p-7 shadow-card transition-shadow hover:shadow-lift">
                  <div className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-[#0a84ff] to-[#5e5ce6] text-white transition-transform duration-500 group-hover:rotate-6 group-hover:scale-110"><Icon className="h-5 w-5" /></div>
                  <h3 className="mt-5 text-lg font-semibold tracking-tight">{t}</h3>
                  <p className="mt-2 text-[15px] leading-relaxed text-muted">{body}</p>
                </div>
              </Tilt>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

export function StepList({ title, steps }: { title: string; steps: { title: string; body: string }[] }) {
  return (
    <section className="bg-raised px-4 py-20 sm:px-6">
      <div className="mx-auto max-w-3xl">
        <h2 className="text-[30px] font-semibold leading-tight tracking-[-0.02em] sm:text-[44px]"><WordReveal text={title} /></h2>
        <ol className="mt-10 space-y-4">
          {steps.map((s, i) => (
            <Reveal key={s.title} i={i}>
              <motion.li whileHover={{ x: 6 }} whileTap={{ scale: 0.98 }} className="flex gap-5 rounded-2xl border border-line bg-white p-6 shadow-card">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#0a84ff] to-[#bf5af2] text-sm font-semibold text-white">{i + 1}</span>
                <div><h3 className="font-semibold">{s.title}</h3><p className="mt-1 text-[15px] leading-relaxed text-muted">{s.body}</p></div>
              </motion.li>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return <p className="mx-auto max-w-3xl px-4 pb-8 text-center text-xs text-muted sm:px-6">{children}</p>;
}
