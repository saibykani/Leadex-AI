"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "framer-motion";
import { Menu, X } from "lucide-react";
import { Logo } from "@/components/ui";
import { ScrollProgress, Spotlight } from "./motion";
import { MarketingStyles } from "./cinema";

export const NAV = [
  { href: "/product", label: "Product" },
  { href: "/voice-agents", label: "Voice Agents" },
  { href: "/lead-generation", label: "Lead Generation" },
  { href: "/website-studio", label: "Website Studio" },
  { href: "/marketplace-info", label: "Marketplace" },
  { href: "/industries", label: "Industries" },
  { href: "/pricing", label: "Pricing" },
  { href: "/docs", label: "Docs" },
];

function SiteNav() {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { scrollY } = useScroll();
  useMotionValueEvent(scrollY, "change", (v) => setScrolled(v > (path === "/" ? window.innerHeight * 0.8 : 12)));
  const dark = path === "/" && !scrolled && !open;
  useEffect(() => setOpen(false), [path]);
  return (
    <header className={`fixed inset-x-0 top-0 z-50 border-b transition-colors duration-300 ${dark ? "border-white/10 bg-[#05060f]/30 text-white backdrop-blur-md [&_nav]:text-white/75 [&_.lx-ink]:text-white" : scrolled || open ? "border-line/70 bg-white/80 backdrop-blur-xl" : "border-transparent bg-white/40 backdrop-blur-md"}`}>
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" aria-label="Leadex AI home" className={dark ? "[&_span]:!text-white" : ""}><Logo /></Link>
        <nav aria-label="Primary" className="hidden items-center gap-1 text-[13px] text-neutral-700 xl:flex">
          {NAV.map((n) => {
            const active = path === n.href;
            return (
              <Link key={n.href} href={n.href} className={`relative rounded-full px-3 py-1.5 transition-colors ${dark ? "hover:text-white" : "hover:text-neutral-900"} ${active && !dark ? "text-neutral-900" : ""}`}>
                {active && <motion.span layoutId="lx-nav-pill" className="absolute inset-0 -z-10 rounded-full bg-raised" transition={{ type: "spring", stiffness: 400, damping: 32 }} />}
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-1 text-sm">
          <Link href="/login" className={`hidden rounded-full px-3 py-2 sm:inline-flex ${dark ? "text-white/80 hover:text-white" : "text-neutral-700 hover:text-neutral-900"}`}>Sign in</Link>
          <motion.div whileTap={{ scale: 0.94 }} className="hidden sm:block">
            <Link href="/contact?type=talk_to_sales" className="group relative mr-1 inline-flex items-center gap-1.5 overflow-hidden rounded-full border border-[#d4af37]/50 bg-[#05060f] px-4 py-2 font-medium text-[#f5e6b8] shadow-[0_6px_20px_rgba(5,6,15,0.25)]">
              <span aria-hidden className="lx-sheen pointer-events-none absolute inset-y-0 -left-1/2 w-1/2 -skew-x-12 bg-gradient-to-r from-transparent via-white/25 to-transparent" />
              <span className="relative h-1.5 w-1.5 rounded-full bg-[#30d158] shadow-[0_0_8px_#30d158]" />
              <span className="relative">Talk to sales</span>
            </Link>
          </motion.div>
          <motion.div whileTap={{ scale: 0.94 }}>
            <Link href="/register" className="inline-flex rounded-full bg-accent px-4 py-2 font-medium text-white hover:bg-accent-strong">Get started</Link>
          </motion.div>
          <motion.button whileTap={{ scale: 0.9 }} onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label={open ? "Close menu" : "Open menu"}
            className={`ml-1 grid h-9 w-9 place-items-center rounded-full xl:hidden ${dark ? "text-white hover:bg-white/10" : "hover:bg-raised"}`}>
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </motion.button>
        </div>
      </div>
      <AnimatePresence>
        {open && (
          <motion.nav aria-label="Mobile" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            className="border-t border-line bg-white px-4 pb-6 pt-2 xl:hidden">
            {[...NAV, { href: "/contact?type=talk_to_sales", label: "Talk to sales" }, { href: "/demo-booking", label: "Book a demo" }, { href: "/login", label: "Sign in" }].map((n, i) => (
              <motion.div key={n.href} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}>
                <Link href={n.href} className="block rounded-xl px-3 py-3 text-[17px] font-medium active:bg-raised">{n.label}</Link>
              </motion.div>
            ))}
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}

const FOOT: { t: string; l: { href: string; label: string; note?: string }[] }[] = [
  { t: "Platform", l: NAV.slice(0, 5) },
  { t: "Company", l: [{ href: "/pricing", label: "Pricing" }, { href: "/industries", label: "Industries" }, { href: "/docs", label: "Docs" }, { href: "/login", label: "Sign in" }] },
  { t: "Legal", l: [{ href: "/privacy", label: "Privacy" }, { href: "/terms", label: "Terms" }, { href: "/cookies", label: "Cookies" }] },
  { t: "Talk to us", l: [{ href: "/contact", label: "Contact" }, { href: "/contact?type=talk_to_sales", label: "Talk to sales" }, { href: "/demo-booking", label: "Book a demo" }, { href: "/contact?type=partnership", label: "Partnerships" }, { href: "/contact?type=support", label: "Careers", note: "We're not hiring yet" }] },
];

function SiteFooter() {
  return (
    <footer className="relative z-[2] overflow-hidden bg-[#05060f] px-4 py-16 text-white sm:px-6">
      <div aria-hidden className="pointer-events-none absolute -top-40 left-1/2 h-80 w-[60rem] -translate-x-1/2 rounded-full bg-[radial-gradient(closest-side,rgba(94,92,230,0.35),transparent)]" />
      <div className="relative mx-auto grid max-w-7xl gap-10 sm:grid-cols-2 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <span className="[&_span]:text-white"><Logo /></span>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-white/60">Discover opportunities. Engage intelligently. Convert businesses.</p>
          <Link href="/contact?type=talk_to_sales" className="mt-6 inline-flex h-11 items-center rounded-full border border-[#d4af37]/50 px-5 text-sm font-medium text-[#f5e6b8] transition-colors hover:bg-[#d4af37]/10">Talk to sales</Link>
        </div>
        {FOOT.map((c) => (
          <div key={c.t}>
            <p className="text-sm font-semibold">{c.t}</p>
            <ul className="mt-3 space-y-2 text-sm text-white/60">
              {c.l.map((n) => n.note
                ? <li key={n.label}><span className="text-white/60">{n.label}</span> <span className="ml-1 rounded-full bg-white/10 px-2 py-0.5 text-[11px] text-white/60">{n.note}</span></li>
                : <li key={n.label}><Link className="hover:text-white" href={n.href}>{n.label}</Link></li>)}
            </ul>
          </div>
        ))}
      </div>
      <p className="relative mx-auto mt-14 max-w-7xl border-t border-white/10 pt-6 text-xs text-white/45">© {new Date().getFullYear()} Leadex AI. Product illustrations on this site are illustrative. Integrations listed are supported integrations, not partnerships or endorsements.</p>
    </footer>
  );
}

export function MarketingShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-x-clip bg-white">
      <MarketingStyles />
      <ScrollProgress />
      <Spotlight />
      <SiteNav />
      <main className="relative z-[2]">{children}</main>
      <SiteFooter />
    </div>
  );
}
