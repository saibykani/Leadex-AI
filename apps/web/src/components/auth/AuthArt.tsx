"use client";
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { useEffect, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import {
  AnimatePresence, motion, useMotionValue, useReducedMotion, useSpring, useTransform, type MotionValue, type PanInfo,
} from "framer-motion";
import { Globe2, PhoneCall, Trophy } from "lucide-react";

const EASE = [0.22, 1, 0.36, 1] as const;

type CardSpec = { src: string; alt: string; pos: string; w: string; depth: number; delay: number; rotate: number };
type Scene = { id: string; label: string; title: string; body: string; icon: typeof Globe2; tint: string; cards: CardSpec[] };

const SCENES: Scene[] = [
  {
    id: "discover", label: "Discover", icon: Globe2, tint: "from-[#64d2ff] to-[#0a84ff]",
    title: "Find the businesses that need you.",
    body: "Map opportunities with full source provenance.",
    cards: [
      { src: "/auth/globe.svg", alt: "", pos: "left-[4%] top-[4%]", w: "w-[48%]", depth: 30, delay: 0, rotate: 0 },
      { src: "/auth/lead-card.svg", alt: "", pos: "right-[2%] top-[22%]", w: "w-[58%]", depth: 55, delay: 0.1, rotate: 4 },
      { src: "/auth/site-card.svg", alt: "", pos: "left-[10%] bottom-[2%]", w: "w-[52%]", depth: 20, delay: 0.2, rotate: -5 },
    ],
  },
  {
    id: "engage", label: "Engage", icon: PhoneCall, tint: "from-[#bf5af2] to-[#5e5ce6]",
    title: "Start conversations that land.",
    body: "AI voice and consent-gated outreach, built in.",
    cards: [
      { src: "/auth/call-card.svg", alt: "", pos: "left-[2%] top-[10%]", w: "w-[64%]", depth: 50, delay: 0, rotate: -4 },
      { src: "/auth/lead-card.svg", alt: "", pos: "right-[0%] top-[44%]", w: "w-[56%]", depth: 30, delay: 0.1, rotate: 3 },
      { src: "/auth/globe.svg", alt: "", pos: "left-[8%] bottom-[0%]", w: "w-[30%]", depth: 15, delay: 0.2, rotate: 0 },
    ],
  },
  {
    id: "convert", label: "Convert", icon: Trophy, tint: "from-[#ff9f0a] to-[#ff375f]",
    title: "Turn interest into revenue.",
    body: "Websites, follow-ups and deals in one workspace.",
    cards: [
      { src: "/auth/site-card.svg", alt: "", pos: "left-[0%] top-[4%]", w: "w-[60%]", depth: 25, delay: 0, rotate: -3 },
      { src: "/auth/deal-card.svg", alt: "", pos: "right-[2%] top-[34%]", w: "w-[50%]", depth: 60, delay: 0.1, rotate: 5 },
      { src: "/auth/call-card.svg", alt: "", pos: "left-[6%] bottom-[0%]", w: "w-[46%]", depth: 20, delay: 0.2, rotate: -2 },
    ],
  },
];

const BLOBS = [
  { c: "#0a84ff", cls: "-left-24 -top-24 h-80 w-80", x: [0, 60, -20, 0], y: [0, 40, 80, 0], d: 18 },
  { c: "#bf5af2", cls: "-right-20 top-10 h-96 w-96", x: [0, -70, 20, 0], y: [0, 60, -30, 0], d: 22 },
  { c: "#ff375f", cls: "bottom-[-6rem] right-10 h-80 w-80", x: [0, -40, 50, 0], y: [0, -60, 10, 0], d: 20 },
  { c: "#ff9f0a", cls: "bottom-10 -left-10 h-64 w-64", x: [0, 50, 10, 0], y: [0, -30, 40, 0], d: 16 },
  { c: "#30d158", cls: "left-1/3 top-1/3 h-56 w-56", x: [0, 40, -50, 0], y: [0, -40, 20, 0], d: 24 },
];

function ParallaxCard({ card, mx, my, reduce }: { card: CardSpec; mx: MotionValue<number>; my: MotionValue<number>; reduce: boolean }) {
  const x = useTransform(mx, (v) => v * card.depth);
  const y = useTransform(my, (v) => v * card.depth);
  const rY = useTransform(mx, (v) => v * 10);
  const rX = useTransform(my, (v) => v * -10);
  return (
    <motion.div
      className={`absolute ${card.pos} ${card.w}`}
      style={reduce ? { rotate: card.rotate } : { x, y, rotateX: rX, rotateY: rY, rotate: card.rotate, transformPerspective: 900 }}
      initial={reduce ? false : { opacity: 0, y: 40, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={reduce ? undefined : { opacity: 0, scale: 0.92, transition: { duration: 0.35 } }}
      transition={{ duration: 0.8, delay: card.delay, ease: EASE }}
    >
      <motion.div
        animate={reduce ? undefined : { y: [0, -10, 0] }}
        transition={{ duration: 5 + card.depth / 20, repeat: Infinity, ease: "easeInOut", delay: card.delay * 4 }}
      >
        <motion.div
          className="group relative cursor-grab"
          whileHover={reduce ? undefined : { y: -8, scale: 1.04 }}
          whileTap={reduce ? undefined : { scale: 0.95 }}
          transition={{ type: "spring", stiffness: 300, damping: 20 }}
        >
          <div className="absolute -inset-3 rounded-[28px] bg-white/40 opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100" />
          <img src={card.src} alt={card.alt} draggable={false} className="relative w-full select-none drop-shadow-[0_24px_40px_rgba(20,10,80,0.45)]" />
        </motion.div>
      </motion.div>
    </motion.div>
  );
}

/** Immersive animated art: aurora blobs, parallax glass cards, rotating Discover → Engage → Convert scenes. */
export function AuthArt({ compact = false }: { compact?: boolean }) {
  const reduce = !!useReducedMotion();
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  const rawX = useMotionValue(0);
  const rawY = useMotionValue(0);
  const mx = useSpring(rawX, { stiffness: 80, damping: 18 });
  const my = useSpring(rawY, { stiffness: 80, damping: 18 });
  const ref = useRef<HTMLDivElement>(null);
  const scene = SCENES[i];

  useEffect(() => {
    if (reduce || paused) return;
    const t = setInterval(() => setI((n) => (n + 1) % SCENES.length), 5000);
    return () => clearInterval(t);
  }, [reduce, paused, i]);

  useEffect(() => {
    if (reduce) return;
    const onTilt = (e: DeviceOrientationEvent) => {
      if (e.gamma == null || e.beta == null) return;
      rawX.set(Math.max(-0.5, Math.min(0.5, e.gamma / 60)));
      rawY.set(Math.max(-0.5, Math.min(0.5, (e.beta - 45) / 60)));
    };
    window.addEventListener("deviceorientation", onTilt);
    return () => window.removeEventListener("deviceorientation", onTilt);
  }, [reduce, rawX, rawY]);

  const onMove = (e: RPointerEvent<HTMLDivElement>) => {
    if (reduce || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    rawX.set((e.clientX - r.left) / r.width - 0.5);
    rawY.set((e.clientY - r.top) / r.height - 0.5);
  };
  const onLeave = () => { rawX.set(0); rawY.set(0); };
  const go = (n: number) => setI((n + SCENES.length) % SCENES.length);
  const onDragEnd = (_: unknown, info: PanInfo) => {
    if (info.offset.x < -50 || info.velocity.x < -400) go(i + 1);
    else if (info.offset.x > 50 || info.velocity.x > 400) go(i - 1);
  };
  const Icon = scene.icon;

  return (
    <div
      ref={ref}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      className={`relative isolate overflow-hidden text-white ${compact ? "h-[360px] rounded-b-[32px]" : "h-full min-h-screen"}`}
    >
      <img src="/auth/aurora.svg" alt="" className="absolute inset-0 -z-20 h-full w-full object-cover" />
      <div className="absolute inset-0 -z-10">
        {BLOBS.map((b, k) => (
          <motion.div
            key={k}
            className={`absolute rounded-full opacity-60 mix-blend-screen blur-3xl ${b.cls}`}
            style={{ background: b.c }}
            animate={reduce ? undefined : { x: b.x, y: b.y, scale: [1, 1.15, 0.95, 1] }}
            transition={{ duration: b.d, repeat: Infinity, ease: "easeInOut" }}
          />
        ))}
      </div>

      <div className={`relative flex h-full flex-col ${compact ? "px-5 pb-16 pt-5" : "p-12 xl:p-14"}`}>
        <Link href="/" className="relative z-10 inline-flex w-fit items-center gap-2 rounded-full text-[17px] font-semibold tracking-tight focus-visible:outline focus-visible:outline-2 focus-visible:outline-white">
          <motion.span
            className="grid h-8 w-8 place-items-center rounded-xl bg-white/20 text-[14px] font-bold ring-1 ring-white/40 backdrop-blur"
            whileHover={{ rotate: 12, scale: 1.1 }} whileTap={{ scale: 0.9 }}
          >L</motion.span>
          Leadex AI
        </Link>

        <motion.div
          className={`relative flex-1 touch-pan-y ${compact ? "my-2" : "my-8"}`}
          drag={reduce ? false : "x"}
          dragConstraints={{ left: 0, right: 0 }}
          dragElastic={0.25}
          onDragEnd={onDragEnd}
          aria-hidden
        >
          <AnimatePresence mode="popLayout">
            <motion.div key={scene.id} className={`absolute inset-0 mx-auto ${compact ? "max-w-[300px]" : "max-w-[520px]"}`}>
              {scene.cards.map((c) => <ParallaxCard key={c.src + c.pos} card={c} mx={mx} my={my} reduce={reduce} />)}
            </motion.div>
          </AnimatePresence>
        </motion.div>

        <div className="relative z-10">
          <AnimatePresence mode="wait">
            <motion.div
              key={scene.id}
              initial={reduce ? false : { opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduce ? undefined : { opacity: 0, y: -10 }}
              transition={{ duration: 0.45, ease: EASE }}
              aria-live="polite"
            >
              <span className={`inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r ${scene.tint} px-3 py-1 text-[12px] font-semibold shadow-lg`}>
                <Icon className="h-3.5 w-3.5" aria-hidden />{scene.label}
              </span>
              {!compact && <h2 className="mt-4 max-w-md text-[38px] font-semibold leading-[1.08] tracking-tight drop-shadow-sm">{scene.title}</h2>}
              <p className={`${compact ? "mt-2 text-[14px]" : "mt-3 text-lg"} text-white/85`}>{compact ? scene.title : scene.body}</p>
            </motion.div>
          </AnimatePresence>

          <div className={`flex items-center gap-2 ${compact ? "mt-3" : "mt-8"}`} role="tablist" aria-label="Feature scenes">
            {SCENES.map((sc, k) => (
              <motion.button
                key={sc.id}
                type="button"
                role="tab"
                aria-selected={k === i}
                aria-label={sc.label}
                onClick={() => go(k)}
                whileHover={{ scale: 1.15 }}
                whileTap={{ scale: 0.85 }}
                className="relative h-2 w-10 overflow-hidden rounded-full bg-white/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
              >
                {k === i && (
                  <motion.span
                    key={`${sc.id}-${paused}`}
                    className="absolute inset-0 origin-left rounded-full bg-white"
                    initial={{ scaleX: reduce || paused ? 1 : 0 }}
                    animate={{ scaleX: 1 }}
                    transition={{ duration: reduce || paused ? 0 : 5, ease: "linear" }}
                  />
                )}
              </motion.button>
            ))}
          </div>
          {!compact && <p className="mt-8 text-sm text-white/60">© {new Date().getFullYear()} Leadex AI</p>}
        </div>
      </div>
    </div>
  );
}
