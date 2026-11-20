"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode, type PointerEvent } from "react";
import {
  animate, motion, useInView, useMotionTemplate, useMotionValue, useReducedMotion, useScroll, useSpring, useTransform,
  type MotionValue, type Variants,
} from "framer-motion";

export const EASE = [0.22, 1, 0.36, 1] as const;

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 32 },
  show: (i: number = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.7, delay: i * 0.08, ease: EASE } }),
};

export function Reveal({ children, i = 0, className }: { children: ReactNode; i?: number; className?: string }) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div variants={fadeUp} custom={i} initial="hidden" whileInView="show" viewport={{ once: true, margin: "-60px" }} className={className}>
      {children}
    </motion.div>
  );
}

/** Splits text into words that rise in sequence when scrolled into view. */
export function WordReveal({ text, className, delay = 0 }: { text: string; className?: string; delay?: number }) {
  const reduce = useReducedMotion();
  const words = text.split(" ");
  return (
    // In-view trigger lives on the unclipped wrapper; words slide up via variants. (Observing the clipped
    // word itself never fired, which left headings permanently invisible.)
    <motion.span
      className={className}
      initial={reduce ? false : "hidden"}
      whileInView="show"
      viewport={{ once: true, amount: 0.2 }}
      variants={{ hidden: {}, show: { transition: { staggerChildren: 0.06, delayChildren: delay } } }}
    >
      <span className="sr-only">{text}</span>
      {words.map((w, i) => (
        <span key={i} aria-hidden className="inline-block overflow-hidden pb-[0.12em] align-bottom">
          <motion.span
            className="inline-block"
            variants={{ hidden: { y: "105%", opacity: 0 }, show: { y: "0%", opacity: 1, transition: { duration: 0.7, ease: EASE } } }}
          >
            {w}
          </motion.span>
          {i < words.length - 1 ? " " : ""}
        </span>
      ))}
    </motion.span>
  );
}

/** Scroll-linked highlight: words go from faint to solid as the paragraph scrolls through. */
export function ScrollText({ text, className }: { text: string; className?: string }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 85%", "end 50%"] });
  const words = text.split(" ");
  return (
    <p ref={ref} className={className}>
      {words.map((w, i) => (
        <ScrollWord key={i} word={w} progress={scrollYProgress} range={[i / words.length, (i + 1) / words.length]} />
      ))}
    </p>
  );
}
function ScrollWord({ word, progress, range }: { word: string; progress: MotionValue<number>; range: [number, number] }) {
  const reduce = useReducedMotion();
  const opacity = useTransform(progress, range, [0.18, 1]);
  return <motion.span style={reduce ? undefined : { opacity }} className="mr-[0.25em] inline-block">{word}</motion.span>;
}

/** Counts up to a real product number (never a fabricated metric). */
export function Counter({ to, className }: { to: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduce = useReducedMotion();
  const [v, setV] = useState(0);
  useEffect(() => {
    if (reduce) { setV(to); return; }
    if (!inView) return;
    const c = animate(0, to, { duration: 1.4, ease: EASE, onUpdate: (n) => setV(Math.round(n)) });
    return () => c.stop();
  }, [inView, reduce, to]);
  return <span ref={ref} className={className}>{v}</span>;
}

/** Pulls toward the pointer while hovered; springs back. Press feedback via whileTap. */
export function Magnetic({ children, className, strength = 0.3 }: { children: ReactNode; className?: string; strength?: number }) {
  const reduce = useReducedMotion();
  const x = useSpring(0, { stiffness: 250, damping: 18 });
  const y = useSpring(0, { stiffness: 250, damping: 18 });
  function move(e: PointerEvent<HTMLDivElement>) {
    if (reduce || e.pointerType !== "mouse") return;
    const r = e.currentTarget.getBoundingClientRect();
    x.set((e.clientX - r.left - r.width / 2) * strength);
    y.set((e.clientY - r.top - r.height / 2) * strength);
  }
  return (
    <motion.div style={{ x, y }} onPointerMove={move} onPointerLeave={() => { x.set(0); y.set(0); }}
      whileTap={{ scale: 0.94 }} className={`inline-block ${className ?? ""}`}>
      {children}
    </motion.div>
  );
}

export function CTA({ href, children, variant = "primary" }: { href: string; children: ReactNode; variant?: "primary" | "ghost" | "white" }) {
  const cls = {
    primary: "bg-accent text-white shadow-[0_8px_24px_rgba(0,113,227,0.35)] hover:bg-accent-strong",
    ghost: "border border-line bg-white/80 text-neutral-900 backdrop-blur hover:bg-raised",
    white: "bg-white text-accent hover:bg-white/90",
  }[variant];
  return (
    <Magnetic>
      <Link href={href} className={`group inline-flex h-12 items-center gap-2 rounded-full px-7 text-[15px] font-medium transition-colors ${cls}`}>
        {children}
      </Link>
    </Magnetic>
  );
}

/** 3D tilt following mouse or touch, with a moving glare. */
export function Tilt({ children, className, max = 10 }: { children: ReactNode; className?: string; max?: number }) {
  const reduce = useReducedMotion();
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);
  const [hover, setHover] = useState(false);
  const rx = useSpring(useTransform(py, [0, 1], [max, -max]), { stiffness: 200, damping: 20 });
  const ry = useSpring(useTransform(px, [0, 1], [-max, max]), { stiffness: 200, damping: 20 });
  const gx = useTransform(px, (v) => `${v * 100}%`);
  const gy = useTransform(py, (v) => `${v * 100}%`);
  const glare = useMotionTemplate`radial-gradient(circle at ${gx} ${gy}, rgba(255,255,255,0.5), transparent 55%)`;
  function move(e: PointerEvent<HTMLDivElement>) {
    if (reduce) return;
    const r = e.currentTarget.getBoundingClientRect();
    px.set((e.clientX - r.left) / r.width);
    py.set((e.clientY - r.top) / r.height);
    setHover(true);
  }
  function reset() { px.set(0.5); py.set(0.5); setHover(false); }
  return (
    <motion.div
      onPointerMove={move} onPointerLeave={reset} onPointerUp={reset} onPointerCancel={reset}
      whileTap={reduce ? undefined : { scale: 0.98 }}
      style={reduce ? undefined : { rotateX: rx, rotateY: ry, transformPerspective: 900 }}
      className={`relative ${className ?? ""}`}
    >
      {children}
      {!reduce && (
        <motion.div aria-hidden style={{ background: glare }} animate={{ opacity: hover ? 1 : 0 }}
          className="pointer-events-none absolute inset-0 rounded-[inherit]" />
      )}
    </motion.div>
  );
}

export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 120, damping: 25 });
  return <motion.div aria-hidden style={{ scaleX }} className="fixed inset-x-0 top-0 z-[60] h-[3px] origin-left bg-gradient-to-r from-[#0a84ff] via-[#5e5ce6] to-[#bf5af2]" />;
}

/** Soft glow following the cursor on fine-pointer devices only. */
export function Spotlight() {
  const reduce = useReducedMotion();
  const [on, setOn] = useState(false);
  const x = useSpring(-600, { stiffness: 120, damping: 20 });
  const y = useSpring(-600, { stiffness: 120, damping: 20 });
  useEffect(() => {
    if (reduce || !window.matchMedia("(pointer: fine)").matches) return;
    setOn(true);
    const h = (e: globalThis.PointerEvent) => { x.set(e.clientX - 250); y.set(e.clientY - 250); };
    window.addEventListener("pointermove", h, { passive: true });
    return () => window.removeEventListener("pointermove", h);
  }, [reduce, x, y]);
  if (!on) return null;
  return (
    <motion.div aria-hidden style={{ x, y }}
      className="pointer-events-none fixed left-0 top-0 z-[40] h-[500px] w-[500px] rounded-full bg-[radial-gradient(circle,rgba(10,132,255,0.10),rgba(191,90,242,0.06)_40%,transparent_70%)]" />
  );
}

/** Animated gradient mesh of drifting blobs (CSS keyframes, paused under reduced motion). */
export function Mesh({ className, dark }: { className?: string; dark?: boolean }) {
  const a = dark ? "opacity-40" : "opacity-70";
  return (
    <div aria-hidden className={`pointer-events-none absolute inset-0 overflow-hidden ${className ?? ""}`}>
      <div className={`lx-blob absolute left-[5%] top-[-10%] h-[22rem] w-[22rem] rounded-full bg-[#0a84ff]/30 blur-3xl sm:h-[28rem] sm:w-[28rem] ${a}`} />
      <div className={`lx-blob lx-delay-2 absolute right-[0%] top-[10%] h-[20rem] w-[20rem] rounded-full bg-[#bf5af2]/25 blur-3xl sm:h-[26rem] sm:w-[26rem] ${a}`} />
      <div className={`lx-blob lx-delay-4 absolute bottom-[-10%] left-[35%] h-[18rem] w-[18rem] rounded-full bg-[#5e5ce6]/25 blur-3xl sm:h-[24rem] sm:w-[24rem] ${a}`} />
    </div>
  );
}

export function SectionHead({ eyebrow, title, body, dark }: { eyebrow: string; title: string; body?: string; dark?: boolean }) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      <Reveal><p className={`text-[15px] font-semibold ${dark ? "text-[#64d2ff]" : "text-accent"}`}>{eyebrow}</p></Reveal>
      <h2 className="mt-3 text-[34px] font-semibold leading-[1.08] tracking-[-0.025em] sm:text-[52px]"><WordReveal text={title} /></h2>
      {body && <Reveal i={2}><p className={`mx-auto mt-5 max-w-2xl text-lg leading-relaxed ${dark ? "text-white/70" : "text-muted"}`}>{body}</p></Reveal>}
    </div>
  );
}

/** Parallax wrapper: moves children at a different rate while scrolling. */
export function Parallax({ children, speed = 60, className }: { children: ReactNode; speed?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], [speed, -speed]);
  return <motion.div ref={ref} style={reduce ? undefined : { y }} className={className}>{children}</motion.div>;
}
