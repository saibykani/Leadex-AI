"use client";
import { useRef, useState } from "react";
import { motion, useMotionValueEvent, useReducedMotion, useScroll, useTransform, type MotionValue } from "framer-motion";
import { Globe2, MapPin, Phone, Sparkles, Trophy } from "lucide-react";
import { BrowserMock, CallCard, ConvertedBadge, GlobeMap, LeadCard, Waveform } from "./illustrations";

const STEPS = [
  { icon: MapPin, k: "Discover", t: "Pins drop where opportunity lives.", b: "Pick a country, city and industry. Leadex finds businesses through compliant sources, including ones with no website, and records where each data point came from." },
  { icon: Sparkles, k: "Qualify", t: "Pins become scored lead cards.", b: "Contacts are verified, consent is recorded and every lead gets an explainable score before anyone reaches out." },
  { icon: Phone, k: "Engage", t: "An AI agent makes the call.", b: "Voice agents qualify, book and follow up, always disclosing they are AI. Email and WhatsApp run through approval gates." },
  { icon: Globe2, k: "Show", t: "A website preview, built for them.", b: "Website Studio generates an industry-specific preview from verified details, so the owner sees value before the pitch." },
  { icon: Trophy, k: "Convert", t: "Deal closed, or referred.", b: "Book the meeting, send the proposal, or match the requirement to a verified provider and track the commission." },
];

function Layer({ p, i, children }: { p: MotionValue<number>; i: number; children: React.ReactNode }) {
  const n = STEPS.length;
  const s = i / n, e = (i + 1) / n, f = 0.06;
  const opacity = useTransform(p, i === 0 ? [0, e - f, e] : i === n - 1 ? [s - f, s, 1] : [s - f, s, e - f, e], i === 0 ? [1, 1, 0] : i === n - 1 ? [0, 1, 1] : [0, 1, 1, 0]);
  const scale = useTransform(p, [s - f, s, e], [0.88, 1, i === n - 1 ? 1 : 1.04]);
  const y = useTransform(p, [s - f, s], [40, 0]);
  return <motion.div style={{ opacity, scale, y }} className="absolute inset-0 grid place-items-center">{children}</motion.div>;
}

/** Pinned scroll story: the product mock transforms across five stages as the user scrolls. */
export function ScrollStory() {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress: p } = useScroll({ target: ref, offset: ["start start", "end end"] });
  const [active, setActive] = useState(0);
  useMotionValueEvent(p, "change", (v) => setActive(Math.min(STEPS.length - 1, Math.max(0, Math.floor(v * STEPS.length)))));
  const rotate = useTransform(p, [0, 1], [-4, 4]);
  const bar = useTransform(p, [0, 1], ["0%", "100%"]);

  if (reduce) {
    return (
      <div className="mx-auto grid max-w-5xl gap-6 px-4 sm:grid-cols-2 sm:px-6">
        {STEPS.map(({ icon: Icon, k, t, b }) => (
          <div key={k} className="card p-6"><Icon className="h-5 w-5 text-accent" /><p className="mt-3 text-sm font-semibold text-accent">{k}</p><h3 className="mt-1 text-xl font-semibold">{t}</h3><p className="mt-2 text-muted">{b}</p></div>
        ))}
      </div>
    );
  }

  return (
    <div ref={ref} className="relative" style={{ height: `${STEPS.length * 75 + 25}vh` }}>
      <div className="sticky top-0 flex h-screen items-center overflow-hidden">
        <div className="mx-auto grid w-full max-w-6xl items-center gap-6 px-4 pt-14 sm:px-6 lg:grid-cols-2 lg:gap-16">
          {/* Copy */}
          <div className="order-2 lg:order-1">
            <div className="mb-5 flex gap-1.5">
              {STEPS.map((s, i) => (
                <span key={s.k} className={`h-1.5 rounded-full transition-all duration-500 ${i === active ? "w-8 bg-accent" : "w-3 bg-line"}`} />
              ))}
            </div>
            <div className="relative min-h-[200px] sm:min-h-[220px]">
              {STEPS.map(({ icon: Icon, k, t, b }, i) => (
                <motion.div key={k} aria-hidden={i !== active} initial={false}
                  animate={{ opacity: i === active ? 1 : 0, y: i === active ? 0 : i < active ? -24 : 24 }}
                  transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                  className={`absolute inset-0 ${i === active ? "" : "pointer-events-none"}`}>
                  <p className="inline-flex items-center gap-2 text-[15px] font-semibold text-accent"><Icon className="h-4 w-4" /> Step {i + 1} · {k}</p>
                  <h3 className="mt-3 text-[28px] font-semibold leading-tight tracking-[-0.02em] sm:text-[40px]">{t}</h3>
                  <p className="mt-4 max-w-lg text-[16px] leading-relaxed text-muted sm:text-lg">{b}</p>
                </motion.div>
              ))}
            </div>
            <div className="mt-6 h-1 w-full max-w-xs overflow-hidden rounded-full bg-line"><motion.div style={{ width: bar }} className="h-full bg-gradient-to-r from-[#0a84ff] to-[#bf5af2]" /></div>
          </div>
          {/* Transforming mock */}
          <motion.div style={{ rotate }} className="relative order-1 mx-auto aspect-square w-full max-w-[300px] sm:max-w-[420px] lg:order-2 lg:max-w-[480px]">
            <div className="absolute inset-[6%] rounded-[40px] bg-gradient-to-br from-[#eaf3ff] via-white to-[#f4ecff] shadow-lift ring-1 ring-line" />
            <Layer p={p} i={0}><GlobeMap className="w-[86%]" /></Layer>
            <Layer p={p} i={1}>
              <div className="w-[78%] space-y-3">
                <LeadCard name="Studio Arc Interiors" tag="Interior design · no website" />
                <LeadCard name="Northside Builders" tag="Construction · verified contact" delay={0.6} />
                <LeadCard name="Green Bowl Kitchen" tag="Restaurant · consent recorded" delay={1.2} />
              </div>
            </Layer>
            <Layer p={p} i={2}>
              <div className="w-[80%] space-y-4">
                <CallCard />
                <div className="flex justify-center"><Waveform bars={16} className="h-10" color="from-[#5e5ce6] to-[#64d2ff]" /></div>
              </div>
            </Layer>
            <Layer p={p} i={3}><BrowserMock className="w-[82%]" title="studioarc.preview" /></Layer>
            <Layer p={p} i={4}>
              <div className="relative">
                <div className="absolute inset-0 -z-10 animate-pulse rounded-full bg-success/20 blur-2xl" />
                <ConvertedBadge />
              </div>
            </Layer>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
