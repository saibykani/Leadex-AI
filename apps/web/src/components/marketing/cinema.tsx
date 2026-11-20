"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  motion, useInView, useMotionValueEvent, useReducedMotion, useScroll, useSpring, useTransform, type MotionValue,
} from "framer-motion";
import {
  ArrowRight, Bot, Building2, CalendarDays, Check, Cpu, Database, FileClock, Globe2, KeyRound, Landmark, Layers, Lock, Mail,
  MapPin, MessageCircle, Phone, Rocket, Scale, Search, ShieldCheck, Sparkles, Trophy, Users,
} from "lucide-react";
import { CTA, Counter, EASE, Magnetic, Reveal, Tilt } from "./motion";
import { BrowserMock, CallCard, ConvertedBadge, GlobeMap, LeadCard, Waveform } from "./illustrations";
import { serif } from "./fonts";
import { ContactForm } from "./contact";
import { money, salesApi, type PublicPlan } from "./sales-api";

const INK = "#05060f";
const GOLD = "#d4af37";
const CHAMPAGNE = "#f5e6b8";

/** Keyframes local to the marketing site (globals.css is owned elsewhere). All paused under reduced motion. */
export function MarketingStyles() {
  return (
    <style>{`
@keyframes lx-sheen-k { 0% { transform: translateX(0) skewX(-12deg); } 60%,100% { transform: translateX(400%) skewX(-12deg); } }
.lx-sheen { animation: lx-sheen-k 4.5s ease-in-out infinite; }
@keyframes lx-aurora-k { 0%,100% { transform: translate3d(0,0,0) rotate(0deg) scale(1); } 50% { transform: translate3d(4%,-3%,0) rotate(8deg) scale(1.08); } }
.lx-aurora { animation: lx-aurora-k 18s ease-in-out infinite; }
@keyframes lx-sweep-k { 0% { transform: translateX(-120%) rotate(12deg); opacity: 0; } 20% { opacity: 1; } 100% { transform: translateX(220%) rotate(12deg); opacity: 0; } }
.lx-sweep { animation: lx-sweep-k 7s cubic-bezier(.22,1,.36,1) 1.2s infinite; }
@keyframes lx-dashflow { to { stroke-dashoffset: -40; } }
.lx-flow { stroke-dasharray: 6 8; animation: lx-dashflow 1.6s linear infinite; }
@keyframes lx-ticker-k { to { transform: translateX(-50%); } }
.lx-ticker { animation: lx-ticker-k 50s linear infinite; }
@media (prefers-reduced-motion: reduce) { .lx-sheen, .lx-aurora, .lx-sweep, .lx-flow, .lx-ticker { animation: none !important; } }
`}</style>
  );
}

/* ------------------------------------------------------------------ starfield (cursor reactive) */
function Starfield() {
  const ref = useRef<HTMLCanvasElement>(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    let w = 0, h = 0, raf = 0, mx = 0.5, my = 0.5, tx = 0.5, ty = 0.5, visible = true;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const n = window.innerWidth < 640 ? 70 : 160;
    const stars = Array.from({ length: n }, () => ({ x: Math.random(), y: Math.random(), z: 0.2 + Math.random() * 0.8, t: Math.random() * 6 }));
    const resize = () => { w = c.clientWidth; h = c.clientHeight; c.width = w * dpr; c.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); };
    const move = (e: PointerEvent) => { tx = e.clientX / window.innerWidth; ty = e.clientY / window.innerHeight; };
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible && !reduce) raf = requestAnimationFrame(draw); });
    function draw(time = 0) {
      mx += (tx - mx) * 0.04; my += (ty - my) * 0.04;
      ctx!.clearRect(0, 0, w, h);
      for (const s of stars) {
        const px = (s.x + (mx - 0.5) * 0.06 * s.z) * w, py = (s.y + (my - 0.5) * 0.06 * s.z) * h;
        const tw = reduce ? 0.7 : 0.45 + 0.55 * Math.abs(Math.sin(time / 1400 + s.t));
        const near = Math.hypot(px - mx * w, py - my * h) < 140 ? 1.8 : 1;
        ctx!.globalAlpha = Math.min(1, tw * s.z * near);
        ctx!.fillStyle = s.z > 0.85 ? CHAMPAGNE : "#cfe3ff";
        ctx!.beginPath(); ctx!.arc(px, py, s.z * 1.3 * near, 0, Math.PI * 2); ctx!.fill();
      }
      if (visible && !reduce) raf = requestAnimationFrame(draw);
    }
    resize(); draw();
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", move, { passive: true });
    io.observe(c);
    return () => { cancelAnimationFrame(raf); io.disconnect(); window.removeEventListener("resize", resize); window.removeEventListener("pointermove", move); };
  }, [reduce]);
  return <canvas ref={ref} aria-hidden className="absolute inset-0 h-full w-full" />;
}

/** Headline line that rises out of a mask with a blur-in. */
function MaskLine({ children, delay, className }: { children: ReactNode; delay: number; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <span className="block overflow-hidden pb-[0.08em]">
      <motion.span className={`block ${className ?? ""}`} initial={reduce ? false : { y: "110%", filter: "blur(12px)", opacity: 0 }}
        animate={{ y: "0%", filter: "blur(0px)", opacity: 1 }} transition={{ duration: 1.2, delay, ease: EASE }}>
        {children}
      </motion.span>
    </span>
  );
}

export function CinematicHero() {
  const ref = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const sceneScale = useTransform(scrollYProgress, [0, 1], [1, 1.18]);
  const sceneY = useTransform(scrollYProgress, [0, 1], [0, -80]);
  const back = useTransform(scrollYProgress, [0, 1], [0, 160]);
  const front = useTransform(scrollYProgress, [0, 1], [0, -160]);
  const copyFade = useTransform(scrollYProgress, [0, 0.6], [1, 0]);
  const copyY = useTransform(scrollYProgress, [0, 0.6], [0, -60]);
  const rx = useSpring(0, { stiffness: 60, damping: 20 });
  const ry = useSpring(0, { stiffness: 60, damping: 20 });
  useEffect(() => {
    if (reduce || !window.matchMedia("(pointer: fine)").matches) return;
    const h = (e: PointerEvent) => { ry.set((e.clientX / window.innerWidth - 0.5) * 10); rx.set(-(e.clientY / window.innerHeight - 0.5) * 8); };
    window.addEventListener("pointermove", h, { passive: true });
    return () => window.removeEventListener("pointermove", h);
  }, [reduce, rx, ry]);
  const st = (v: object) => (reduce ? undefined : v);
  return (
    <section ref={ref} className="relative min-h-[100svh] overflow-hidden text-white" style={{ background: `radial-gradient(120% 80% at 50% 0%, #0b1028 0%, ${INK} 60%)` }}>
      <Starfield />
      {/* aurora */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="lx-aurora absolute -left-[10%] top-[-20%] h-[38rem] w-[38rem] rounded-full bg-[#0a84ff]/25 blur-[110px]" />
        <div className="lx-aurora absolute right-[-10%] top-[5%] h-[34rem] w-[34rem] rounded-full bg-[#bf5af2]/20 blur-[110px]" style={{ animationDelay: "-6s" }} />
        <div className="lx-aurora absolute bottom-[-25%] left-[30%] h-[30rem] w-[40rem] rounded-full bg-[#5e5ce6]/25 blur-[120px]" style={{ animationDelay: "-11s" }} />
        <div className="lx-sweep absolute -top-1/4 left-0 h-[150%] w-40 bg-gradient-to-r from-transparent via-white/[0.07] to-transparent" />
      </div>
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(255,255,255,0.035)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.035)_1px,transparent_1px)] bg-[size:64px_64px] [mask-image:radial-gradient(ellipse_at_50%_30%,black_20%,transparent_70%)]" />

      <motion.div style={st({ opacity: copyFade, y: copyY })} className="relative mx-auto max-w-6xl px-4 pt-32 text-center sm:px-6 sm:pt-40">
        <motion.div initial={reduce ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.1 }}
          className="mx-auto inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-[13px] backdrop-blur" style={{ borderColor: `${GOLD}55`, color: CHAMPAGNE, background: "rgba(255,255,255,0.03)" }}>
          <Sparkles className="h-3.5 w-3.5" /> The AI business growth platform
        </motion.div>
        <h1 className={`${serif.className} mx-auto mt-8 max-w-5xl text-[54px] leading-[0.95] tracking-[-0.01em] sm:text-[96px] lg:text-[118px]`}>
          <MaskLine delay={0.25}>Discover. Engage.</MaskLine>
          <MaskLine delay={0.5} className="bg-gradient-to-r from-[#64d2ff] via-[#a5a3ff] to-[#f5e6b8] bg-clip-text italic text-transparent">Convert at scale.</MaskLine>
        </h1>
        <motion.p initial={reduce ? false : { opacity: 0, y: 16, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} transition={{ duration: 1, delay: 0.85 }}
          className="mx-auto mt-7 max-w-2xl text-[17px] leading-relaxed text-white/65 sm:text-xl">
          Leadex finds the businesses you should be talking to, engages them with consent-checked AI voice, email and live website previews, and carries every deal to the finish line. One secure, multi-tenant platform.
        </motion.p>
        <motion.div initial={reduce ? false : { opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, delay: 1.05 }} className="mt-10 flex flex-wrap justify-center gap-3">
          <CTA href="/register">Start free trial <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" /></CTA>
          <Magnetic>
            <Link href="/contact?type=talk_to_sales" className="group relative inline-flex h-12 items-center gap-2 overflow-hidden rounded-full border px-7 text-[15px] font-medium" style={{ borderColor: `${GOLD}80`, color: CHAMPAGNE }}>
              <span aria-hidden className="lx-sheen pointer-events-none absolute inset-y-0 -left-1/2 w-1/2 bg-gradient-to-r from-transparent via-white/20 to-transparent" />
              <span className="relative">Talk to sales</span>
            </Link>
          </Magnetic>
        </motion.div>
      </motion.div>

      {/* Layered product scene */}
      <motion.div style={st({ scale: sceneScale, y: sceneY })} className="relative mx-auto mt-14 h-[360px] max-w-5xl px-4 [perspective:1400px] sm:mt-16 sm:h-[460px]">
        <motion.div initial={reduce ? false : { opacity: 0, y: 80, rotateX: 25 }} animate={{ opacity: 1, y: 0, rotateX: 0 }} transition={{ duration: 1.6, delay: 0.7, ease: EASE }}
          style={st({ rotateX: rx, rotateY: ry })} className="relative h-full [transform-style:preserve-3d]">
          <motion.div style={st({ y: back })} className="absolute left-1/2 top-0 w-[290px] -translate-x-1/2 sm:w-[420px]">
            <div className="rounded-[40px] border border-white/10 bg-white/[0.06] p-4 shadow-[0_40px_120px_-20px_rgba(10,132,255,0.45)] backdrop-blur-md">
              <div className="rounded-[30px] bg-white p-3"><GlobeMap className="w-full" /></div>
            </div>
          </motion.div>
          <motion.div style={st({ y: front })} className="absolute left-0 top-12 hidden w-64 [transform:translateZ(80px)] md:block"><LeadCard name="Studio Arc Interiors" tag="Interior design · no website" /></motion.div>
          <motion.div style={st({ y: front })} className="absolute right-0 top-28 hidden w-64 [transform:translateZ(120px)] md:block"><CallCard /></motion.div>
          <motion.div style={st({ y: front })} className="absolute bottom-2 left-[5%] hidden w-56 [transform:translateZ(60px)] lg:block"><BrowserMock title="preview" /></motion.div>
          <div className="lx-float absolute bottom-8 right-[5%] hidden items-center gap-2 rounded-2xl border border-white/15 bg-white/10 px-4 py-3 text-white backdrop-blur md:flex">
            <ShieldCheck className="h-5 w-5 text-[#30d158]" /><span className="text-sm font-medium">Consent verified</span>
          </div>
        </motion.div>
      </motion.div>
      <p className="relative pb-6 text-center text-[11px] text-white/35">Illustrative product visuals.</p>
      <div aria-hidden className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-b from-transparent to-white" />
    </section>
  );
}

/* ------------------------------------------------------------------ chapters */
const CHAPTERS = [
  { icon: MapPin, k: "Discover", t: "Find the businesses worth your time.", b: "Search by country, city, locality and industry, including businesses with no website. Every data point keeps its source and timestamp.", tint: "#0a84ff" },
  { icon: Phone, k: "Engage", t: "Start conversations that disclose they're AI.", b: "Voice agents qualify and book; email and WhatsApp go through consent checks and approval gates before anything is sent.", tint: "#5e5ce6" },
  { icon: Trophy, k: "Convert", t: "Show value before the pitch, then close.", b: "Generate a website preview from verified details, move the deal through 17 tracked stages, or refer it for a commission.", tint: "#bf5af2" },
  { icon: Rocket, k: "Scale", t: "Run it for one team, or for many tenants.", b: "Workflows automate the repetitive steps. Each organization's data is isolated, so you can serve other businesses on the same platform.", tint: GOLD },
];

function Scene({ p, i, children }: { p: MotionValue<number>; i: number; children: ReactNode }) {
  const n = CHAPTERS.length, s = i / n, e = (i + 1) / n, f = 0.07;
  const opacity = useTransform(p, i === 0 ? [0, e - f, e] : i === n - 1 ? [s - f, s, 1] : [s - f, s, e - f, e], i === 0 ? [1, 1, 0] : i === n - 1 ? [0, 1, 1] : [0, 1, 1, 0]);
  const scale = useTransform(p, [s - f, s, e], [0.86, 1, i === n - 1 ? 1 : 1.06]);
  const blur = useTransform(p, [s - f, s, e - f, e], ["blur(10px)", "blur(0px)", "blur(0px)", i === n - 1 ? "blur(0px)" : "blur(8px)"]);
  return <motion.div style={{ opacity, scale, filter: blur }} className="absolute inset-0 grid place-items-center">{children}</motion.div>;
}

export function Chapters() {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress: p } = useScroll({ target: ref, offset: ["start start", "end end"] });
  const [active, setActive] = useState(0);
  useMotionValueEvent(p, "change", (v) => setActive(Math.min(CHAPTERS.length - 1, Math.max(0, Math.floor(v * CHAPTERS.length)))));
  const rail = useTransform(p, [0, 1], ["0%", "100%"]);
  const rotate = useTransform(p, [0, 1], [-5, 5]);

  if (reduce) {
    return (
      <div className="mx-auto grid max-w-5xl gap-5 px-4 py-16 sm:grid-cols-2 sm:px-6">
        {CHAPTERS.map(({ icon: Icon, k, t, b }) => (
          <div key={k} className="rounded-3xl border border-line bg-white p-7 shadow-card"><Icon className="h-5 w-5 text-accent" /><p className="mt-3 text-sm font-semibold text-accent">{k}</p><h3 className="mt-1 text-xl font-semibold">{t}</h3><p className="mt-2 text-muted">{b}</p></div>
        ))}
      </div>
    );
  }
  return (
    <div ref={ref} className="relative" style={{ height: `${CHAPTERS.length * 85 + 20}vh` }}>
      <div className="sticky top-0 flex h-[100svh] items-center overflow-hidden">
        {/* progress rail */}
        <div className="absolute left-4 top-1/2 hidden h-64 -translate-y-1/2 sm:left-8 md:block">
          <div className="relative h-full w-px bg-line"><motion.div style={{ height: rail }} className="absolute left-0 top-0 w-px bg-gradient-to-b from-[#0a84ff] via-[#5e5ce6] to-[#d4af37]" /></div>
          {CHAPTERS.map((c, i) => (
            <div key={c.k} className="absolute -left-[5px] flex items-center gap-3" style={{ top: `${(i / (CHAPTERS.length - 1)) * 100}%`, transform: "translateY(-50%)" }}>
              <span className={`h-[11px] w-[11px] rounded-full border-2 transition-all duration-500 ${i <= active ? "scale-110 border-white" : "border-line bg-white"}`} style={i <= active ? { background: c.tint } : undefined} />
              <span className={`text-xs font-semibold uppercase tracking-[0.18em] transition-opacity ${i === active ? "opacity-100" : "opacity-40"}`}>{c.k}</span>
            </div>
          ))}
        </div>
        <div className="mx-auto grid w-full max-w-6xl items-center gap-6 px-4 pt-14 sm:px-6 md:pl-36 lg:grid-cols-2 lg:gap-14">
          <div className="order-2 lg:order-1">
            <div className="mb-4 flex gap-1.5 md:hidden">
              {CHAPTERS.map((c, i) => <span key={c.k} className={`h-1.5 rounded-full transition-all duration-500 ${i === active ? "w-8 bg-accent" : "w-3 bg-line"}`} />)}
            </div>
            <div className="relative min-h-[230px]">
              {CHAPTERS.map(({ icon: Icon, k, t, b, tint }, i) => (
                <motion.div key={k} aria-hidden={i !== active} initial={false}
                  animate={{ opacity: i === active ? 1 : 0, y: i === active ? 0 : i < active ? -30 : 30, filter: i === active ? "blur(0px)" : "blur(6px)" }}
                  transition={{ duration: 0.6, ease: EASE }} className={`absolute inset-0 ${i === active ? "" : "pointer-events-none"}`}>
                  <p className="inline-flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.2em]" style={{ color: tint === GOLD ? "#a8841f" : tint }}><Icon className="h-4 w-4" /> Chapter {i + 1} · {k}</p>
                  <h3 className={`${serif.className} mt-3 text-[38px] leading-[1.02] sm:text-[56px]`}>{t}</h3>
                  <p className="mt-4 max-w-lg text-[16px] leading-relaxed text-muted sm:text-lg">{b}</p>
                </motion.div>
              ))}
            </div>
          </div>
          <motion.div style={{ rotate }} className="relative order-1 mx-auto aspect-square w-full max-w-[290px] sm:max-w-[420px] lg:order-2 lg:max-w-[480px]">
            <div className="absolute inset-[6%] rounded-[44px] bg-gradient-to-br from-[#eaf3ff] via-white to-[#f7efff] shadow-lift ring-1 ring-line" />
            <Scene p={p} i={0}><GlobeMap className="w-[86%]" /></Scene>
            <Scene p={p} i={1}>
              <div className="w-[80%] space-y-4"><CallCard /><div className="flex justify-center"><Waveform bars={18} className="h-10" color="from-[#5e5ce6] to-[#64d2ff]" /></div></div>
            </Scene>
            <Scene p={p} i={2}>
              <div className="relative w-[82%]"><BrowserMock title="studioarc.preview" /><div className="absolute -bottom-6 -right-4"><ConvertedBadge /></div></div>
            </Scene>
            <Scene p={p} i={3}>
              <div className="grid w-[78%] grid-cols-2 gap-3">
                {["Acme Realty", "Northside Builders", "Green Bowl", "Studio Arc"].map((n, j) => (
                  <div key={n} className="rounded-2xl border border-line bg-white p-3 shadow-card">
                    <div className="flex items-center gap-2"><span className="grid h-7 w-7 place-items-center rounded-lg text-[11px] font-bold text-white" style={{ background: ["#0a84ff", "#5e5ce6", "#bf5af2", GOLD][j] }}>{n[0]}</span><span className="truncate text-[12px] font-semibold">{n}</span></div>
                    <div className="mt-2 flex items-center gap-1 text-[10px] text-muted"><Lock className="h-3 w-3" /> isolated tenant</div>
                  </div>
                ))}
              </div>
            </Scene>
          </motion.div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ architecture & security */
const PILLARS = [
  { icon: Database, t: "Tenant isolation", b: "PostgreSQL row-level security on every tenant table; the app's database role cannot bypass it." },
  { icon: ShieldCheck, t: "Consent-gated outreach", b: "Calls, emails and WhatsApp are checked against consent, suppression lists and kill switches first." },
  { icon: FileClock, t: "Audit logs", b: "Sensitive actions are recorded with actor, time and target." },
  { icon: KeyRound, t: "Encrypted secrets", b: "Integration credentials and MFA secrets are encrypted at rest, with key-rotation support." },
  { icon: Cpu, t: "Open-source AI", b: "Runs on open models you can self-host (e.g. Ollama). Paid providers are opt-in." },
  { icon: Scale, t: "Country-aware rules", b: "Jurisdiction profiles set calling windows, DNC registries and recording rules." },
];

function ArchDiagram() {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  const draw = { initial: { pathLength: 0 }, animate: inView ? { pathLength: 1 } : {}, transition: { duration: 1.4, ease: EASE } };
  const tenants = [["Tenant A", 70], ["Tenant B", 160], ["Tenant C", 250]] as const;
  return (
    <svg ref={ref} viewBox="0 0 560 320" className="w-full" role="img" aria-label="Diagram: each tenant's requests pass the consent gate and row-level security before reaching its own isolated data">
      <defs>
        <linearGradient id="lxg" x1="0" x2="1"><stop offset="0" stopColor="#0a84ff" /><stop offset="0.6" stopColor="#5e5ce6" /><stop offset="1" stopColor="#d4af37" /></linearGradient>
      </defs>
      {tenants.map(([n, y], i) => (
        <g key={n}>
          <motion.rect initial={{ opacity: 0, x: -20 }} animate={inView ? { opacity: 1, x: 0 } : {}} transition={{ delay: i * 0.15 }} x="10" y={y - 22} width="110" height="44" rx="14" fill="rgba(255,255,255,0.06)" stroke="rgba(255,255,255,0.18)" />
          <text x="65" y={y + 5} textAnchor="middle" fill="#fff" fontSize="13" fontWeight="600">{n}</text>
          <motion.path {...draw} d={`M120 ${y} C 170 ${y}, 170 160, 220 160`} stroke="url(#lxg)" strokeWidth="2" fill="none" />
          <path d={`M120 ${y} C 170 ${y}, 170 160, 220 160`} className="lx-flow" stroke="rgba(255,255,255,0.35)" strokeWidth="1.2" fill="none" />
        </g>
      ))}
      <motion.g initial={{ opacity: 0, scale: 0.9 }} animate={inView ? { opacity: 1, scale: 1 } : {}} transition={{ delay: 0.5 }} style={{ transformOrigin: "280px 160px" }}>
        <rect x="220" y="110" width="120" height="100" rx="22" fill="rgba(212,175,55,0.08)" stroke="#d4af37" strokeOpacity="0.7" />
        <text x="280" y="148" textAnchor="middle" fill={CHAMPAGNE} fontSize="12" fontWeight="700" letterSpacing="1.5">GATE</text>
        <text x="280" y="168" textAnchor="middle" fill="#fff" fontSize="11">consent · suppression</text>
        <text x="280" y="184" textAnchor="middle" fill="#fff" fontSize="11">kill switch · hours</text>
      </motion.g>
      {tenants.map(([n, y], i) => (
        <g key={`db-${n}`}>
          <motion.path {...draw} transition={{ duration: 1.2, delay: 0.7 + i * 0.1, ease: EASE }} d={`M340 160 C 390 160, 390 ${y}, 440 ${y}`} stroke="url(#lxg)" strokeWidth="2" fill="none" />
          <path d={`M340 160 C 390 160, 390 ${y}, 440 ${y}`} className="lx-flow" stroke="rgba(255,255,255,0.3)" strokeWidth="1.2" fill="none" />
          <motion.g initial={{ opacity: 0, x: 20 }} animate={inView ? { opacity: 1, x: 0 } : {}} transition={{ delay: 1 + i * 0.12 }}>
            <ellipse cx="490" cy={y - 12} rx="46" ry="9" fill="rgba(10,132,255,0.25)" stroke="rgba(255,255,255,0.25)" />
            <path d={`M444 ${y - 12} v26 a46 9 0 0 0 92 0 v-26`} fill="rgba(10,132,255,0.12)" stroke="rgba(255,255,255,0.25)" />
            <text x="490" y={y + 9} textAnchor="middle" fill="#fff" fontSize="11">RLS · {n.slice(-1)} only</text>
          </motion.g>
        </g>
      ))}
    </svg>
  );
}

export function Architecture() {
  return (
    <section className="relative overflow-hidden px-4 py-28 text-white sm:px-6" style={{ background: `linear-gradient(180deg, ${INK}, #0b1028 60%, ${INK})` }}>
      <div aria-hidden className="lx-aurora pointer-events-none absolute -right-40 top-10 h-[30rem] w-[30rem] rounded-full bg-[#5e5ce6]/20 blur-[120px]" />
      <div className="relative mx-auto max-w-6xl">
        <Reveal><p className="text-[13px] font-semibold uppercase tracking-[0.22em]" style={{ color: CHAMPAGNE }}>Architecture & trust</p></Reveal>
        <div className="mt-4 grid items-center gap-12 lg:grid-cols-2">
          <div>
            <h2 className={`${serif.className} text-[44px] leading-[1.0] sm:text-[64px]`}>Enterprise-grade by construction, <span className="italic text-white/60">not by promise.</span></h2>
            <p className="mt-6 max-w-lg text-lg text-white/65">Security and compliance are built into the data layer and the outreach path, so every team on Leadex inherits them automatically.</p>
          </div>
          <Reveal i={1}><div className="rounded-[32px] border border-white/10 bg-white/[0.03] p-5 backdrop-blur sm:p-8"><ArchDiagram /></div></Reveal>
        </div>
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PILLARS.map(({ icon: Icon, t, b }, i) => (
            <Reveal key={t} i={i % 3}>
              <Tilt className="h-full rounded-3xl" max={6}>
                <div className="group h-full rounded-3xl border border-white/10 bg-white/[0.04] p-7 transition-colors hover:border-[#d4af37]/40">
                  <Icon className="h-6 w-6 transition-colors group-hover:text-[#f5e6b8]" style={{ color: "#64d2ff" }} />
                  <h3 className="mt-5 text-lg font-semibold">{t}</h3>
                  <p className="mt-2 text-[15px] leading-relaxed text-white/60">{b}</p>
                </div>
              </Tilt>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ integrations + built for */
const INTEGRATIONS = [
  { icon: MapPin, n: "Google Places", d: "Business discovery" }, { icon: Mail, n: "Gmail", d: "Email (OAuth)" }, { icon: Mail, n: "Outlook", d: "Email (OAuth)" },
  { icon: MessageCircle, n: "WhatsApp Business", d: "Official Cloud API" }, { icon: Phone, n: "Twilio", d: "Voice & telephony" }, { icon: Landmark, n: "Stripe", d: "Payments" },
  { icon: Landmark, n: "Razorpay", d: "Payments" }, { icon: Bot, n: "Ollama", d: "Self-hosted AI" },
];

export function Integrations() {
  return (
    <section className="px-4 py-28 sm:px-6">
      <div className="mx-auto max-w-6xl text-center">
        <Reveal><p className="text-[15px] font-semibold text-accent">Integrations</p></Reveal>
        <h2 className={`${serif.className} mt-3 text-[42px] leading-[1.02] sm:text-[60px]`}>Plugs into the tools you already run.</h2>
        <p className="mx-auto mt-4 max-w-xl text-muted">Supported integrations. Listing a service here does not imply a partnership or endorsement.</p>
      </div>
      <div className="mx-auto mt-12 grid max-w-5xl grid-cols-2 gap-3 sm:grid-cols-4">
        {INTEGRATIONS.map(({ icon: Icon, n, d }, i) => (
          <Reveal key={n} i={i % 4}>
            <Tilt className="rounded-3xl" max={10}>
              <div className="flex h-full flex-col items-center rounded-3xl border border-line bg-white p-6 text-center shadow-card transition-shadow hover:shadow-lift">
                <span className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-[#f2f6ff] to-[#f6efff] text-accent ring-1 ring-line"><Icon className="h-5 w-5" /></span>
                <p className="mt-4 font-semibold">{n}</p><p className="text-xs text-muted">{d}</p>
              </div>
            </Tilt>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

export function BuiltFor({ names }: { names: string[] }) {
  return (
    <section aria-label="Built for" className="border-y border-line bg-white py-7">
      <div className="mx-auto flex max-w-7xl items-center gap-8 px-4 sm:px-6">
        <p className="hidden shrink-0 text-[11px] font-semibold uppercase tracking-[0.22em] text-neutral-400 sm:block">Built for</p>
        <div className="overflow-hidden [mask-image:linear-gradient(90deg,transparent,black_8%,black_92%,transparent)]">
          <div className="lx-ticker flex w-max gap-12">
            {[...names, ...names].map((x, i) => <span key={i} aria-hidden={i >= names.length} className={`${serif.className} whitespace-nowrap text-2xl text-neutral-400`}>{x}</span>)}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ why now + capabilities */
const WHY = [
  { icon: Layers, t: "Growth stacks are fragmented", b: "Teams stitch together lead lists, dialers, CRMs, website builders and spreadsheets. Leadex runs the whole journey in one place." },
  { icon: Cpu, t: "Open AI models are now good enough", b: "Capable open-source models make AI agents affordable to run at scale, and self-hostable for data-sensitive teams." },
  { icon: Scale, t: "Compliance is tightening", b: "Consent and do-not-call rules keep evolving. Outreach tools need compliance in the core, not bolted on." },
  { icon: Building2, t: "Local businesses are under-served", b: "Many small businesses still lack a website or digital presence; showing them a preview is a new way to open the conversation." },
];
// Verified against the codebase: agents/templates.py (10), websites/templates.py (11), crm STATUSES (17),
// compliance DEFAULT_PROFILES (7 incl. the strictest default).
const CAPS = [{ n: 10, l: "AI agent templates" }, { n: 11, l: "website templates" }, { n: 17, l: "tracked lead stages" }, { n: 7, l: "jurisdiction profiles" }];

export function WhyNow() {
  return (
    <section className="relative overflow-hidden px-4 py-28 sm:px-6">
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#d4af37]/50 to-transparent" />
      <div className="mx-auto max-w-6xl">
        <div className="grid gap-10 lg:grid-cols-[1fr_1.2fr]">
          <div>
            <Reveal><p className="text-[13px] font-semibold uppercase tracking-[0.22em] text-[#a8841f]">Why now</p></Reveal>
            <h2 className={`${serif.className} mt-3 text-[44px] leading-[1.0] sm:text-[64px]`}>The moment for an <span className="italic">all-in-one</span> growth platform.</h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {WHY.map(({ icon: Icon, t, b }, i) => (
              <Reveal key={t} i={i}>
                <motion.div whileHover={{ y: -6 }} className="h-full rounded-3xl border border-line bg-white p-6 shadow-card">
                  <Icon className="h-5 w-5 text-accent" /><h3 className="mt-4 font-semibold">{t}</h3><p className="mt-1.5 text-[15px] leading-relaxed text-muted">{b}</p>
                </motion.div>
              </Reveal>
            ))}
          </div>
        </div>
        <div className="mt-16 grid grid-cols-2 gap-px overflow-hidden rounded-[28px] border border-line bg-line lg:grid-cols-4">
          {CAPS.map((c) => (
            <div key={c.l} className="bg-white p-7 text-center">
              <Counter to={c.n} className={`${serif.className} bg-gradient-to-br from-[#0a84ff] via-[#5e5ce6] to-[#bf5af2] bg-clip-text text-6xl text-transparent sm:text-7xl`} />
              <p className="mt-1 text-sm text-muted">{c.l}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-center text-xs text-muted">Product capabilities shipped in the platform today. Not customer or usage metrics.</p>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ pricing teaser + talk to sales */
export function PricingTeaser() {
  const [plans, setPlans] = useState<PublicPlan[] | null>(null);
  useEffect(() => { salesApi.pricing().then((r) => setPlans(r.plans.slice(0, 3))).catch(() => setPlans([])); }, []);
  return (
    <section className="px-4 py-24 sm:px-6">
      <div className="mx-auto grid max-w-6xl items-center gap-10 lg:grid-cols-[1fr_1.4fr]">
        <div>
          <Reveal><p className="text-[15px] font-semibold text-accent">Pricing</p></Reveal>
          <h2 className={`${serif.className} mt-3 text-[44px] leading-[1.0] sm:text-[60px]`}>Start free. Scale when you're ready.</h2>
          <p className="mt-5 max-w-md text-lg text-muted">Every plan includes data isolation, the compliance layer and open-source AI. Compare real limits side by side.</p>
          <div className="mt-8 flex flex-wrap gap-3"><CTA href="/pricing">See pricing <ArrowRight className="h-4 w-4" /></CTA><CTA href="/register" variant="ghost">Start free trial</CTA></div>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {(plans ?? [null, null, null]).map((p, i) => (
            <Reveal key={p?.code ?? i} i={i}>
              <Tilt className="h-full rounded-3xl" max={8}>
                <Link href="/pricing" className={`block h-full rounded-3xl border p-6 shadow-card transition-shadow hover:shadow-lift ${p?.highlight ? "border-accent bg-gradient-to-b from-[#f2f7ff] to-white" : "border-line bg-white"}`}>
                  {p ? (
                    <>
                      <p className="font-semibold">{p.name}</p>
                      <p className={`${serif.className} mt-6 text-[34px] leading-none`}>{p.price_monthly && !p.contact_sales ? money(p.price_monthly, p.currency) : "Contact sales"}</p>
                      <p className="mt-1 text-xs text-muted">{p.price_monthly && !p.contact_sales ? "per month" : "price on request"}</p>
                      <ul className="mt-5 space-y-1.5 text-[13px] text-muted">
                        {p.features.slice(0, 3).map((f) => <li key={f} className="flex gap-1.5"><Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-accent" />{f}</li>)}
                      </ul>
                    </>
                  ) : <div className="h-44 animate-pulse rounded-2xl bg-raised" />}
                </Link>
              </Tilt>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

export function TalkToSales() {
  return (
      <section id="talk-to-sales" className="relative scroll-mt-16 overflow-hidden px-4 py-28 text-white sm:px-6 bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950">
        <div aria-hidden className="lx-aurora pointer-events-none absolute -left-32 bottom-0 h-[28rem] w-[28rem] rounded-full bg-[#0a84ff]/20 blur-[110px]" />
        <div aria-hidden className="pointer-events-none absolute right-0 top-0 h-72 w-72 rounded-full bg-[#d4af37]/10 blur-[90px]" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
          <div>
            <Reveal><p className="text-xs font-semibold uppercase tracking-wider text-blue-400">Direct Consultation</p></Reveal>
            <h2 className={`${serif.className} mt-4 text-[46px] leading-[0.98] sm:text-[68px]`}>Connect with the team <span className="italic text-white/60">behind Leadex.</span></h2>
            <p className="mt-6 max-w-lg text-lg text-white/65">Tell us what you're building. We'll help you plan a rollout, size the right plan, or set up white-label for your clients.</p>
            <ul className="mt-8 space-y-3 text-[15px] text-white/80">
              {[[Users, "A real person reads every request"], [CalendarDays, "Prefer a call? Book a demo slot instantly"], [Globe2, "We aim to reply within 1 business day"]].map(([Icon, t]) => {
                const I = Icon as typeof Users;
                return <li key={t as string} className="flex items-center gap-3"><span className="grid h-8 w-8 place-items-center rounded-full border border-white/15"><I className="h-4 w-4 text-emerald-400" /></span>{t as string}</li>;
              })}
            </ul>
            <div className="mt-8 flex flex-wrap gap-3 text-sm">
              <Link href="/demo-booking" className="inline-flex h-11 items-center gap-2 rounded-full border border-white/20 px-5 hover:bg-white/10"><CalendarDays className="h-4 w-4 text-blue-400" />Book a demo</Link>
              <Link href="/contact?type=partnership" className="inline-flex h-11 items-center gap-2 rounded-full border border-white/20 px-5 hover:bg-white/10"><Search className="h-4 w-4 text-emerald-400" />Partnerships</Link>
            </div>
          </div>
          <Reveal i={1}><ContactForm compact dark /></Reveal>
        </div>
      </section>
      );
}
