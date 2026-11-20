"use client";
import { motion, useReducedMotion } from "framer-motion";
import { Bot, CheckCircle2, MapPin, Phone, Star, User } from "lucide-react";

/** Stylised globe with latitude lines and pulsing discovery pins. Pure SVG. */
export function GlobeMap({ className }: { className?: string }) {
  const pins = [[120, 90], [200, 140], [150, 190], [255, 95], [90, 160], [230, 205]];
  return (
    <svg viewBox="0 0 340 300" className={className} role="img" aria-label="Illustration of a globe with discovery pins">
      <defs>
        <radialGradient id="lxg" cx="35%" cy="30%"><stop offset="0" stopColor="#e8f2ff" /><stop offset="1" stopColor="#c9dcff" /></radialGradient>
        <linearGradient id="lxp" x1="0" x2="1"><stop offset="0" stopColor="#0a84ff" /><stop offset="1" stopColor="#5e5ce6" /></linearGradient>
      </defs>
      <circle cx="170" cy="150" r="125" fill="url(#lxg)" />
      <g className="lx-spin-slow" style={{ transformOrigin: "170px 150px" }} fill="none" stroke="#0a84ff" strokeOpacity="0.18">
        {[30, 60, 90, 115].map((rx) => <ellipse key={rx} cx="170" cy="150" rx={rx} ry="125" />)}
      </g>
      <g fill="none" stroke="#0a84ff" strokeOpacity="0.15">
        {[-80, -40, 0, 40, 80].map((d) => <ellipse key={d} cx="170" cy={150 + d} rx={Math.sqrt(125 ** 2 - d ** 2)} ry="10" />)}
      </g>
      <path d="M120 90 Q 160 60 200 140 T 230 205" fill="none" stroke="url(#lxp)" strokeWidth="1.5" className="lx-dash" />
      {pins.map(([x, y], i) => (
        <g key={i}>
          <circle cx={x} cy={y} r="9" fill="#0a84ff" opacity="0.35" className="lx-ping" style={{ animationDelay: `${i * 0.35}s` }} />
          <circle cx={x} cy={y} r="5" fill="url(#lxp)" stroke="#fff" strokeWidth="2" />
        </g>
      ))}
    </svg>
  );
}

/** Voice waveform bars. */
export function Waveform({ bars = 28, className, color = "from-[#0a84ff] to-[#bf5af2]" }: { bars?: number; className?: string; color?: string }) {
  return (
    <div aria-hidden className={`flex h-16 items-center gap-[3px] ${className ?? ""}`}>
      {Array.from({ length: bars }).map((_, i) => (
        <span key={i} className={`lx-wave block h-full w-[4px] rounded-full bg-gradient-to-t ${color}`}
          style={{ animationDelay: `${(i * 97) % 1100 / 1000}s`, opacity: 0.5 + ((i * 37) % 50) / 100 }} />
      ))}
    </div>
  );
}

/** Browser window with a generated website preview. */
export function BrowserMock({ className, title = "yourbusiness.preview" }: { className?: string; title?: string }) {
  return (
    <div className={`overflow-hidden rounded-2xl border border-line bg-white shadow-lift ${className ?? ""}`}>
      <div className="flex items-center gap-2 border-b border-line bg-raised px-3 py-2">
        <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" /><span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" /><span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        <span className="ml-2 truncate rounded-md bg-white px-2 py-0.5 text-[11px] text-muted">{title}</span>
      </div>
      <div className="p-4">
        <div className="h-24 rounded-xl bg-gradient-to-br from-[#0a84ff] via-[#5e5ce6] to-[#bf5af2] p-3">
          <div className="h-2.5 w-24 rounded bg-white/90" /><div className="mt-2 h-2 w-36 rounded bg-white/60" />
          <div className="mt-4 h-5 w-16 rounded-full bg-white" />
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="rounded-lg bg-raised p-2"><div className="h-8 rounded bg-white" /><div className="mt-1.5 h-1.5 w-3/4 rounded bg-line" /></div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** Chat bubbles between an AI agent and a prospect (illustrative copy). */
export function ChatBubbles({ className }: { className?: string }) {
  const reduce = useReducedMotion();
  const msgs = [
    { me: false, t: "Hi, this is an AI assistant calling on behalf of Leadex. Is now a good time?" },
    { me: true, t: "Sure, what is it about?" },
    { me: false, t: "We built a free website preview for your studio. Can I send the link?" },
    { me: true, t: "Yes, please send it over." },
  ];
  return (
    <div className={`space-y-2.5 ${className ?? ""}`}>
      {msgs.map((m, i) => (
        <motion.div key={i} initial={reduce ? false : { opacity: 0, y: 12, scale: 0.96 }} whileInView={{ opacity: 1, y: 0, scale: 1 }}
          viewport={{ once: true }} transition={{ delay: i * 0.35, duration: 0.45 }}
          className={`flex items-end gap-2 ${m.me ? "justify-end" : ""}`}>
          {!m.me && <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#0a84ff] to-[#5e5ce6] text-white"><Bot className="h-3.5 w-3.5" /></span>}
          <p className={`max-w-[78%] rounded-2xl px-3.5 py-2 text-[13px] leading-snug ${m.me ? "rounded-br-sm bg-accent text-white" : "rounded-bl-sm bg-raised text-neutral-800"}`}>{m.t}</p>
          {m.me && <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-line text-muted"><User className="h-3.5 w-3.5" /></span>}
        </motion.div>
      ))}
    </div>
  );
}

/** Funnel shape, stages only (no numbers). */
export function Funnel({ className }: { className?: string }) {
  const stages = ["Discovered", "Verified", "Approved", "Engaged", "Converted"];
  const reduce = useReducedMotion();
  return (
    <div className={`space-y-2 ${className ?? ""}`}>
      {stages.map((s, i) => (
        <motion.div key={s} initial={reduce ? false : { scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }}
          transition={{ duration: 0.9, delay: i * 0.12, ease: [0.22, 1, 0.36, 1] }}
          style={{ width: `${100 - i * 15}%` }}
          className="mx-auto flex h-10 items-center justify-center rounded-xl bg-gradient-to-r from-[#0a84ff] to-[#5e5ce6] text-[13px] font-medium text-white"
        >{s}</motion.div>
      ))}
    </div>
  );
}

/** Network graph of providers around a central requirement. */
export function NetworkGraph({ className }: { className?: string }) {
  const nodes = [
    { x: 60, y: 60, l: "Architect" }, { x: 280, y: 50, l: "Builder" }, { x: 300, y: 200, l: "Broker" },
    { x: 50, y: 210, l: "Interior" }, { x: 170, y: 255, l: "Contractor" },
  ];
  return (
    <svg viewBox="0 0 340 290" className={className} role="img" aria-label="Network of matched service providers">
      <defs><linearGradient id="lxn" x1="0" x2="1"><stop offset="0" stopColor="#0a84ff" /><stop offset="1" stopColor="#bf5af2" /></linearGradient></defs>
      {nodes.map((n, i) => <line key={i} x1="170" y1="140" x2={n.x} y2={n.y} stroke="url(#lxn)" strokeWidth="1.5" className="lx-dash" />)}
      <circle cx="170" cy="140" r="34" fill="#0a84ff" opacity="0.2" className="lx-ping" />
      <circle cx="170" cy="140" r="30" fill="url(#lxn)" />
      <text x="170" y="144" textAnchor="middle" fontSize="11" fill="#fff" fontWeight="600">Requirement</text>
      {nodes.map((n, i) => (
        <g key={n.l} className="lx-float" style={{ animationDelay: `${i * 0.6}s` }}>
          <rect x={n.x - 38} y={n.y - 14} width="76" height="28" rx="14" fill="#fff" stroke="#e5e5ea" />
          <text x={n.x} y={n.y + 4} textAnchor="middle" fontSize="11" fill="#1d1d1f">{n.l}</text>
        </g>
      ))}
    </svg>
  );
}

export function LeadCard({ name, tag, delay = 0 }: { name: string; tag: string; delay?: number }) {
  return (
    <div className="lx-float flex items-center gap-3 rounded-2xl border border-line bg-white/95 p-3 shadow-card backdrop-blur" style={{ animationDelay: `${delay}s` }}>
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent-soft text-accent"><MapPin className="h-4 w-4" /></span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-semibold">{name}</p>
        <p className="truncate text-[11px] text-muted">{tag}</p>
      </div>
      <Star className="h-4 w-4 text-[#ff9f0a]" />
    </div>
  );
}

export function CallCard() {
  return (
    <div className="rounded-2xl border border-line bg-white p-4 shadow-lift">
      <div className="flex items-center gap-2 text-[13px] font-medium"><Phone className="h-4 w-4 text-accent" /> AI agent on call <span className="ml-auto h-2 w-2 rounded-full bg-success" /></div>
      <Waveform bars={22} className="mt-3 h-12" />
    </div>
  );
}

export function ConvertedBadge() {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-line bg-white px-5 py-4 shadow-lift">
      <span className="grid h-10 w-10 place-items-center rounded-full bg-success/10 text-success"><CheckCircle2 className="h-6 w-6" /></span>
      <div><p className="text-[15px] font-semibold">Converted</p><p className="text-[12px] text-muted">Meeting booked, proposal sent</p></div>
    </div>
  );
}
