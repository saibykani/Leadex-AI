"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  ArrowRight, Bot, Building2, CheckCircle2, ChevronRight, Globe2, MapPin,
  Phone, Play, ShieldCheck, Sparkles, Star, Users, Zap
} from "lucide-react";
import { EASE, Magnetic } from "./motion";
import { serif } from "./fonts";

export function LuminousHero() {
  const reduce = useReducedMotion();
  const [activeTab, setActiveTab] = useState<"discovery" | "voice" | "website">("discovery");
  const [isPlayingVoice, setIsPlayingVoice] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveTab((prev) => (prev === "discovery" ? "voice" : prev === "voice" ? "website" : "discovery"));
    }, 6000);
    return () => clearInterval(timer);
  }, []);

  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-[#f8faff] via-white to-[#f4f7fc] pb-24 pt-32 sm:pt-40 lg:pb-32">
      {/* Ambient background glows with natural luminous colors */}
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/2 h-[600px] w-[1000px] -translate-x-1/2 rounded-full bg-gradient-to-tr from-blue-200/40 via-indigo-100/30 to-sky-100/40 blur-[130px]" />
        <div className="absolute -left-20 top-60 h-[400px] w-[400px] rounded-full bg-blue-100/50 blur-[100px]" />
        <div className="absolute -right-20 top-80 h-[450px] w-[450px] rounded-full bg-emerald-100/40 blur-[110px]" />
        {/* Subtle grid pattern for engineering precision */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#e2e8f0_1px,transparent_1px),linear-gradient(to_bottom,#e2e8f0_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] opacity-40" />
      </div>

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6">
        {/* Top announcement pill */}
        <motion.div
          initial={reduce ? false : { opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: EASE }}
          className="mx-auto flex w-max max-w-full items-center gap-2 rounded-full border border-blue-200/70 bg-white/80 px-4 py-1.5 shadow-[0_2px_10px_rgba(37,99,235,0.06)] backdrop-blur-md"
        >
          <span className="flex h-2 w-2 rounded-full bg-blue-600 animate-pulse" />
          <span className="text-xs font-semibold uppercase tracking-wider text-blue-700">Leadex AI</span>
          <span className="hidden text-slate-300 sm:inline">|</span>
          <span className="hidden text-xs font-medium text-slate-600 sm:inline">The Autonomous Sales Intelligence &amp; Outreach Platform</span>
          <ChevronRight className="h-3 w-3 text-slate-400" />
        </motion.div>

        {/* Hero headline */}
        <div className="mx-auto mt-8 max-w-4xl text-center">
          <motion.h1
            initial={reduce ? false : { opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.1, ease: EASE }}
            className={`${serif.className} text-[44px] leading-[1.05] tracking-[-0.02em] text-slate-900 sm:text-[72px] lg:text-[88px]`}
          >
            Discover unlisted businesses. <br className="hidden sm:inline" />
            <span className="bg-gradient-to-r from-blue-600 via-indigo-600 to-emerald-600 bg-clip-text italic text-transparent">
              Convert with live proof.
            </span>
          </motion.h1>

          <motion.p
            initial={reduce ? false : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.25, ease: EASE }}
            className="mx-auto mt-7 max-w-2xl text-lg leading-relaxed text-slate-600 sm:text-xl"
          >
            Find local businesses that lack a web presence, verify multi-jurisdiction compliance with{" "}
            <span className="font-semibold text-slate-900">OutreachGate</span>, engage them via natural{" "}
            <span className="font-semibold text-slate-900">AI voice agents</span>, and show them an instant website preview before you ever ask for the sale.
          </motion.p>

          {/* Action CTAs */}
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4, ease: EASE }}
            className="mt-10 flex flex-wrap items-center justify-center gap-4"
          >
            <Magnetic>
              <Link
                href="/register"
                className="group inline-flex h-13 items-center gap-2 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 px-8 py-3.5 text-[15px] font-semibold text-white shadow-[0_10px_30px_rgba(37,99,235,0.3)] transition-all hover:scale-[1.02] hover:shadow-[0_14px_40px_rgba(37,99,235,0.4)]"
              >
                <span>Start 14-day free trial</span>
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Magnetic>

            <Magnetic>
              <a
                href="#interactive-tour"
                className="inline-flex h-13 items-center gap-2.5 rounded-full border border-slate-200/90 bg-white/90 px-7 py-3.5 text-[15px] font-semibold text-slate-800 shadow-sm backdrop-blur-md transition-all hover:border-slate-300 hover:bg-slate-50"
              >
                <Play className="h-4 w-4 fill-blue-600 text-blue-600" />
                <span>Explore interactive tour</span>
              </a>
            </Magnetic>
          </motion.div>

          {/* Trust points */}
          <motion.div
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.55 }}
            className="mt-8 flex flex-wrap items-center justify-center gap-6 text-xs font-medium text-slate-500"
          >
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" /> PostgreSQL RLS Isolation
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" /> $0 AI Tokens with Local Ollama
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" /> TRAI & TCPA Default-BLOCK
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" /> No credit card required
            </span>
          </motion.div>
        </div>

        {/* Multi-layered Realistic Product UI Canvas */}
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 0.45, ease: EASE }}
          className="relative mx-auto mt-14 max-w-6xl rounded-3xl border border-slate-200/80 bg-white/70 p-3 shadow-[0_25px_70px_rgba(15,23,42,0.08)] backdrop-blur-xl sm:p-5"
        >
          {/* Top window chrome */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/70 pb-3 px-2">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-rose-400" />
              <span className="h-3 w-3 rounded-full bg-amber-400" />
              <span className="h-3 w-3 rounded-full bg-emerald-400" />
              <span className="ml-3 font-mono text-xs text-slate-400">leadex.workspace / illustrative preview</span>
            </div>

            {/* Quick interactive tab switcher */}
            <div className="flex rounded-xl bg-slate-100 p-1 text-xs font-medium text-slate-600">
              <button
                onClick={() => setActiveTab("discovery")}
                className={`rounded-lg px-3 py-1.5 transition-all ${
                  activeTab === "discovery" ? "bg-white text-slate-900 shadow-sm" : "hover:text-slate-900"
                }`}
              >
                1. Discovery & Provenance
              </button>
              <button
                onClick={() => setActiveTab("voice")}
                className={`rounded-lg px-3 py-1.5 transition-all ${
                  activeTab === "voice" ? "bg-white text-slate-900 shadow-sm" : "hover:text-slate-900"
                }`}
              >
                2. AI Voice
              </button>
              <button
                onClick={() => setActiveTab("website")}
                className={`rounded-lg px-3 py-1.5 transition-all ${
                  activeTab === "website" ? "bg-white text-slate-900 shadow-sm" : "hover:text-slate-900"
                }`}
              >
                3. Instant Website Studio
              </button>
            </div>

            <div className="flex items-center gap-2 text-xs font-semibold text-emerald-600">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-ping" />
              <span>OutreachGate Active</span>
            </div>
          </div>

          {/* Main Visual Display */}
          <div className="mt-4 grid gap-6 lg:grid-cols-12">
            {/* Left 8 Cols: Main Realistic Dashboard Panel */}
            <div className="lg:col-span-8 rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm">
              {activeTab === "discovery" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2">
                      <MapPin className="h-4 w-4 text-blue-600" />
                      <span className="text-sm font-semibold text-slate-900">Google Places API Discovery Job</span>
                      <span className="rounded-md bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">
                        source: google_places
                      </span>
                    </div>
                    <span className="text-xs text-slate-500">24 results in Pune & Mumbai</span>
                  </div>

                  {/* Business items */}
                  <div className="space-y-2.5">
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-blue-200/80 bg-blue-50/40 p-3.5 transition-all hover:bg-blue-50/70">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 shrink-0 overflow-hidden rounded-lg bg-slate-100">
                          <img
                            src="https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=120&q=80"
                            alt="Studio Arc"
                            className="h-full w-full object-cover"
                          />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-900 text-sm">Studio Arc Interior Design</span>
                            <span className="rounded-full bg-amber-100 px-2 py-0.2 text-[10px] font-bold text-amber-800">
                              4.9 ★ (128 reviews)
                            </span>
                          </div>
                          <p className="text-xs text-slate-500">Koregaon Park, Pune • Phone verified • No Website detected</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="rounded-lg bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">
                          Lead Score: 96
                        </span>
                        <span className="rounded-lg bg-blue-600 px-2.5 py-1 text-xs font-medium text-white shadow-sm">
                          Gen Preview
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200/80 bg-white p-3.5 transition-all hover:border-slate-300">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 shrink-0 overflow-hidden rounded-lg bg-slate-100">
                          <img
                            src="https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=120&q=80"
                            alt="Apex Realty"
                            className="h-full w-full object-cover"
                          />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-900 text-sm">Apex Luxury Realty Advisors</span>
                            <span className="rounded-full bg-amber-100 px-2 py-0.2 text-[10px] font-bold text-amber-800">
                              4.8 ★ (94 reviews)
                            </span>
                          </div>
                          <p className="text-xs text-slate-500">Bandra West, Mumbai • Mobile site broken (Speed 34/100)</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="rounded-lg bg-blue-100 px-2.5 py-1 text-xs font-semibold text-blue-800">
                          Lead Score: 91
                        </span>
                        <span className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700">
                          Audit Report
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200/80 bg-white p-3.5 transition-all hover:border-slate-300">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 shrink-0 overflow-hidden rounded-lg bg-slate-100">
                          <img
                            src="https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=120&q=80"
                            alt="Solarium"
                            className="h-full w-full object-cover"
                          />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-900 text-sm">Solarium Fine Dining & Lounge</span>
                            <span className="rounded-full bg-amber-100 px-2 py-0.2 text-[10px] font-bold text-amber-800">
                              4.7 ★ (210 reviews)
                            </span>
                          </div>
                          <p className="text-xs text-slate-500">Kalyani Nagar, Pune • Missing reservation menu link</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="rounded-lg bg-blue-100 px-2.5 py-1 text-xs font-semibold text-blue-800">
                          Lead Score: 88
                        </span>
                        <span className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700">
                          Audit Report
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "voice" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2">
                      <Phone className="h-4 w-4 text-emerald-600 animate-pulse" />
                      <span className="text-sm font-semibold text-slate-900">AI Call Session</span>
                      <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                        Status: Connected (00:38)
                      </span>
                    </div>
                    <button
                      onClick={() => setIsPlayingVoice(!isPlayingVoice)}
                      className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-slate-800"
                    >
                      {isPlayingVoice ? "Pause Stream" : "Simulate Audio"}
                    </button>
                  </div>

                  {/* Audio Waveform */}
                  <div className="rounded-xl bg-slate-900 p-4 text-white">
                    <div className="flex items-center justify-between text-xs text-slate-400">
                      <span>Stream: 24kHz OPUS • Latency: 420ms</span>
                      <span className="text-emerald-400 font-mono">Twilio speech → Ollama → Twilio voice</span>
                    </div>
                    <div className="mt-4 flex h-12 items-center justify-center gap-1">
                      {Array.from({ length: 32 }).map((_, i) => (
                        <span
                          key={i}
                          className="w-1.5 rounded-full bg-gradient-to-t from-blue-500 to-emerald-400 transition-all duration-300"
                          style={{
                            height: isPlayingVoice
                              ? `${20 + Math.sin(i * 0.5 + Date.now() / 200) * 35}%`
                              : `${25 + ((i * 17) % 50)}%`,
                          }}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Dialog transcript */}
                  <div className="space-y-2 rounded-xl bg-slate-50 p-3 text-xs leading-relaxed">
                    <p className="text-blue-700">
                      <span className="font-bold">AI Voice Agent:</span> &ldquo;Hello! I&apos;m an automated assistant calling on behalf of Studio Arc. We noticed your studio has 128 five-star reviews in Koregaon Park but lacks a dedicated web portfolio. We built a free preview of what your site could look like—may I share the link via WhatsApp?&rdquo;
                    </p>
                    <p className="text-slate-800">
                      <span className="font-bold">Studio Founder:</span> &ldquo;Yes, absolutely. Please send it to this number.&rdquo;
                    </p>
                  </div>
                </div>
              )}

              {activeTab === "website" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2">
                      <Globe2 className="h-4 w-4 text-indigo-600" />
                      <span className="text-sm font-semibold text-slate-900">Website Studio Live Preview Canvas</span>
                      <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700">
                        Generated in 1.4s • SeaweedFS S3
                      </span>
                    </div>
                    <span className="text-xs font-semibold text-emerald-600">Ready to Publish</span>
                  </div>

                  {/* Responsive preview frame */}
                  <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-inner">
                    <div className="relative h-56 w-full overflow-hidden">
                      <img
                        src="https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1000&q=80"
                        alt="Preview Website"
                        className="h-full w-full object-cover transition-transform duration-700 hover:scale-105"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-slate-900/80 via-slate-900/30 to-transparent p-5 flex flex-col justify-end text-white">
                        <span className="rounded-full bg-blue-500/80 backdrop-blur-md px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider w-max">
                          Architectural Showcase Template
                        </span>
                        <h4 className="mt-1 text-lg font-bold">Studio Arc Architecture & Interiors</h4>
                        <p className="text-xs text-slate-200">Bespoke residential villas, penthouse transformations & hospitality interiors.</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Right 4 Cols: Live Intelligence & Compliance Widgets */}
            <div className="lg:col-span-4 space-y-4">
              {/* OutreachGate Compliance Card */}
              <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Compliance Gate</span>
                  <span className="flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700">
                    <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" /> PASS
                  </span>
                </div>
                <div className="mt-3 space-y-1.5 text-xs text-slate-600">
                  <div className="flex justify-between">
                    <span>Jurisdiction:</span>
                    <span className="font-medium text-slate-900">India (TRAI / DPDP)</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Suppression list:</span>
                    <span className="font-medium text-emerald-600">Cleared ✓</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Calling Hours:</span>
                    <span className="font-medium text-slate-900">10:45 AM (Valid)</span>
                  </div>
                  <div className="flex justify-between">
                    <span>AI Disclosure Script:</span>
                    <span className="font-medium text-emerald-600">Enforced ✓</span>
                  </div>
                </div>
              </div>

              {/* CRM Deal Pipeline Card */}
              <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Active CRM Pipeline</span>
                  <span className="text-[11px] font-semibold text-blue-600">Stage 9 of 17</span>
                </div>
                <div className="mt-2.5">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-900 text-sm">Studio Arc Deal</span>
                    <span className="font-bold text-slate-900 text-sm">₹45,000</span>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">Status: Website preview delivered</p>

                  <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full w-3/5 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600" />
                  </div>
                  <p className="mt-2 text-[11px] text-slate-400">Next Action: Scheduled follow-up in 24 hours</p>
                </div>
              </div>

              {/* Referral Commission Card */}
              <div className="rounded-2xl border border-slate-200/80 bg-gradient-to-br from-indigo-50/60 to-blue-50/60 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-indigo-700">Referral Marketplace</span>
                  <Sparkles className="h-4 w-4 text-indigo-600" />
                </div>
                <p className="mt-2 text-xs font-medium text-slate-700">
                  Matched with <span className="font-bold text-slate-900">Vertex Builders</span> for ₹85 Lakh commercial interior contract.
                </p>
                <div className="mt-2 text-[11px] font-bold text-indigo-600">
                  Estimated Referral Fee: ₹2,10,000 (2.5%)
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

