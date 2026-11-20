"use client";
import Link from "next/link";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowRight, Bot, Building2, CheckCircle2, ChevronRight, Filter, Globe2, Handshake,
  Layers, Lock, MapPin, Phone, Play, Pause, RefreshCw, Search, ShieldAlert,
  ShieldCheck, Sparkles, Star, UserCheck, Users, Volume2, Workflow, Zap
} from "lucide-react";
import { EASE, Magnetic } from "./motion";
import { serif } from "./fonts";

const TOUR_STAGES = [
  { id: "discovery", number: "01", name: "Intelligent Discovery", badge: "Google Places API" },
  { id: "compliance", number: "02", name: "OutreachGate Compliance", badge: "7 Jurisdictions" },
  { id: "voice", number: "03", name: "AI Voice Agents", badge: "AI disclosure first" },
  { id: "website", number: "04", name: "Instant Website Studio", badge: "Live Previews" },
  { id: "crm", number: "05", name: "17-Stage Lead CRM", badge: "PostgreSQL RLS" },
  { id: "marketplace", number: "06", name: "Referral Marketplace", badge: "Automated Commissions" },
];

export function InteractivePlatformTour() {
  const [activeStage, setActiveStage] = useState(0);
  const [selectedCountry, setSelectedCountry] = useState<"IN" | "US" | "UK" | "AE">("IN");
  const [isPlayingVoice, setIsPlayingVoice] = useState(false);
  const [selectedIndustry, setSelectedIndustry] = useState<"architecture" | "realestate" | "dining" | "dental">("architecture");
  const [deviceViewport, setDeviceViewport] = useState<"desktop" | "mobile">("desktop");

  const stage = TOUR_STAGES[activeStage];

  return (
    <section id="interactive-tour" className="relative scroll-mt-20 overflow-hidden bg-white py-24 sm:py-32">
      {/* Background ambient lighting */}
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 right-0 h-[500px] w-[500px] rounded-full bg-blue-50/70 blur-[120px]" />
        <div className="absolute bottom-10 left-10 h-[450px] w-[450px] rounded-full bg-emerald-50/60 blur-[130px]" />
      </div>

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6">
        {/* Section Header */}
        <div className="mx-auto max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50/70 px-4 py-1 text-xs font-semibold text-blue-700">
            <Sparkles className="h-3.5 w-3.5 text-blue-600" /> Complete Sales Journey Sandbox
          </div>
          <h2 className={`${serif.className} mt-4 text-[38px] leading-[1.08] tracking-tight text-slate-900 sm:text-[56px]`}>
            Every stage of growth, <br className="hidden sm:inline" />
            <span className="italic text-blue-600">orchestrated in one platform.</span>
          </h2>
          <p className="mt-4 text-base leading-relaxed text-slate-600 sm:text-lg">
            Experience how Leadex unifies lead discovery, regulatory compliance, conversational AI, and instant website delivery without switching between 6 different subscriptions.
          </p>
        </div>

        {/* Stage Selector Tabs */}
        <div className="mt-12 flex overflow-x-auto pb-2 scrollbar-none sm:justify-center">
          <div className="flex gap-2 rounded-2xl border border-slate-200/80 bg-slate-50/80 p-1.5 backdrop-blur-md">
            {TOUR_STAGES.map((s, index) => {
              const active = activeStage === index;
              return (
                <button
                  key={s.id}
                  onClick={() => setActiveStage(index)}
                  className={`group relative flex items-center gap-2.5 whitespace-nowrap rounded-xl px-4 py-2.5 text-xs font-semibold transition-all ${active ? "text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
                    }`}
                >
                  {active && (
                    <motion.div
                      layoutId="tour-tab-indicator"
                      className="absolute inset-0 rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70"
                      transition={{ type: "spring", stiffness: 450, damping: 35 }}
                    />
                  )}
                  <span className={`relative text-[11px] font-mono ${active ? "text-blue-600 font-bold" : "text-slate-400"}`}>
                    {s.number}
                  </span>
                  <span className="relative">{s.name}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Dynamic Interactive Stage Viewer */}
        <div className="mt-8 overflow-hidden rounded-3xl border border-slate-200/90 bg-slate-50/50 p-4 shadow-[0_20px_60px_rgba(15,23,42,0.05)] sm:p-8">
          <AnimatePresence mode="wait">
            {/* 01: Intelligent Discovery & Provenance */}
            {stage.id === "discovery" && (
              <motion.div
                key="discovery"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.4, ease: EASE }}
                className="grid gap-8 lg:grid-cols-12 items-center"
              >
                <div className="lg:col-span-5 space-y-5">
                  <div className="inline-flex items-center gap-2 rounded-lg bg-blue-100/70 px-3 py-1 text-xs font-semibold text-blue-800">
                    <Search className="h-3.5 w-3.5 text-blue-600" /> Phase 3: Discovery Engine
                  </div>
                  <h3 className={`${serif.className} text-3xl font-semibold text-slate-900 sm:text-4xl`}>
                    Find high-value businesses with complete data provenance.
                  </h3>
                  <p className="text-slate-600 leading-relaxed text-sm sm:text-base">
                    Discover companies across countries, cities, and localities. Leadex flags businesses lacking websites or suffering from broken mobile experiences, and attributes every field to its source with collection timestamps.
                  </p>

                  <div className="space-y-2.5 text-xs text-slate-600">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                      <span>Zero scraping: Strictly compliant with Google Maps Platform terms.</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                      <span>Every field stores provenance (<code className="font-mono text-slate-800">source, collected_at</code>).</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                      <span>Instant automated website audit (Speed, Mobile Friendly, SSL).</span>
                    </div>
                  </div>

                  <div className="pt-2">
                    <Link
                      href="/lead-generation"
                      className="inline-flex items-center gap-2 text-sm font-semibold text-blue-600 hover:text-blue-700"
                    >
                      Explore discovery specification <ArrowRight className="h-4 w-4" />
                    </Link>
                  </div>
                </div>

                <div className="lg:col-span-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2">
                      <MapPin className="h-4 w-4 text-blue-600" />
                      <span className="font-semibold text-slate-900 text-sm">Target Region: Pune & Mumbai, India</span>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                      Query SKU: Places (New)
                    </span>
                  </div>

                  {/* Sample Business Discovery Cards */}
                  <div className="mt-4 space-y-3">
                    {[
                      {
                        name: "Studio Arc Interiors",
                        locality: "Koregaon Park, Pune",
                        rating: "4.9 ★ (128 reviews)",
                        status: "No Website Detected",
                        statusColor: "bg-rose-50 text-rose-700 border-rose-200",
                        score: 96,
                        img: "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=150&q=80",
                      },
                      {
                        name: "Moda Vista Architectural Design",
                        locality: "Juhu, Mumbai",
                        rating: "4.8 ★ (86 reviews)",
                        status: "Unresponsive Site (Speed 28)",
                        statusColor: "bg-amber-50 text-amber-700 border-amber-200",
                        score: 92,
                        img: "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=150&q=80",
                      },
                      {
                        name: "Heritage Stonework & Construction",
                        locality: "Shivajinagar, Pune",
                        rating: "4.7 ★ (64 reviews)",
                        status: "Missing Mobile Portfolio",
                        statusColor: "bg-blue-50 text-blue-700 border-blue-200",
                        score: 89,
                        img: "https://images.unsplash.com/photo-1541888946425-d0fbb18086f6?auto=format&fit=crop&w=150&q=80",
                      },
                    ].map((biz) => (
                      <div
                        key={biz.name}
                        className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200/80 p-3.5 hover:border-blue-400 hover:shadow-sm transition-all"
                      >
                        <div className="flex items-center gap-3">
                          <img loading="lazy" decoding="async" src={biz.img} alt={biz.name} className="h-11 w-11 rounded-lg object-cover" />
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-slate-900 text-sm">{biz.name}</span>
                              <span className="text-xs text-amber-600 font-medium">{biz.rating}</span>
                            </div>
                            <p className="text-xs text-slate-500">{biz.locality}</p>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <span className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${biz.statusColor}`}>
                            {biz.status}
                          </span>
                          <span className="rounded-lg bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700">
                            Score {biz.score}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-4 flex items-center justify-between rounded-xl bg-slate-50 p-3 text-[11px] text-slate-500">
                    <span>Provenance: Verified via Place ID ChIJ...83kd • Collected: Today, 10:14 AM</span>
                    <span className="font-medium text-blue-600">Retention: 30-day cached ID rule</span>
                  </div>
                </div>
              </motion.div>
            )}

            {/* 02: OutreachGate Compliance Engine */}
            {stage.id === "compliance" && (
              <motion.div
                key="compliance"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.4, ease: EASE }}
                className="grid gap-8 lg:grid-cols-12 items-center"
              >
                <div className="lg:col-span-5 space-y-5">
                  <div className="inline-flex items-center gap-2 rounded-lg bg-emerald-100/70 px-3 py-1 text-xs font-semibold text-emerald-800">
                    <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" /> Phase 2 & 5: Compliance Core
                  </div>
                  <h3 className={`${serif.className} text-3xl font-semibold text-slate-900 sm:text-4xl`}>
                    Default-BLOCK safety across 7 global jurisdictions.
                  </h3>
                  <p className="text-slate-600 leading-relaxed text-sm sm:text-base">
                    No phone call, email, or WhatsApp message leaves the platform without passing through the <code className="font-mono text-slate-900">compliance.OutreachGate</code>. An uncertain lawful basis, off-hours timing, or missing evidence immediately halts outreach.
                  </p>

                  <div className="flex gap-2">
                    {[
                      { code: "IN", label: "India (TRAI / DPDP)" },
                      { code: "US", label: "USA (TCPA / FCC)" },
                      { code: "UK", label: "UK (PECR / ICO)" },
                      { code: "AE", label: "UAE (TDRA)" },
                    ].map((c) => (
                      <button
                        key={c.code}
                        onClick={() => setSelectedCountry(c.code as any)}
                        className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition-all ${selectedCountry === c.code
                            ? "bg-slate-900 text-white shadow-sm"
                            : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"
                          }`}
                      >
                        {c.code}
                      </button>
                    ))}
                  </div>

                  <div className="space-y-2 text-xs text-slate-600">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      <span>Calling window check: Only dials between 09:00 and 20:00 local time.</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      <span>Scrubbed against TRAI NCPR, US National DNC, UK TPS & CTPS.</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      <span>Immediate global and per-tenant kill switches override all actions.</span>
                    </div>
                  </div>
                </div>

                <div className="lg:col-span-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2">
                      <Lock className="h-4 w-4 text-emerald-600" />
                      <span className="font-semibold text-slate-900 text-sm">
                        Live Policy Inspection: {selectedCountry === "IN" ? "India Profile (TRAI TCCCPR 2018)" : selectedCountry === "US" ? "USA Profile (TCPA & TSR)" : selectedCountry === "UK" ? "UK Profile (PECR & GDPR)" : "UAE Profile"}
                      </span>
                    </div>
                    <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-800">
                      GATE: ALLOW
                    </span>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-xl border border-slate-200/80 p-3 bg-slate-50/50">
                      <span className="text-[11px] font-semibold uppercase text-slate-500">Lawful Basis Check</span>
                      <p className="mt-1 font-semibold text-slate-900 text-sm">Legitimate Business Interest</p>
                      <p className="mt-0.5 text-[11px] text-slate-500">Public commercial directory entry verified</p>
                    </div>

                    <div className="rounded-xl border border-slate-200/80 p-3 bg-slate-50/50">
                      <span className="text-[11px] font-semibold uppercase text-slate-500">DNC Registry Scrub</span>
                      <p className="mt-1 font-semibold text-emerald-600 text-sm">Not Listed in National DNC</p>
                      <p className="mt-0.5 text-[11px] text-slate-500">Scrubbed against central registry at 10:14 AM</p>
                    </div>

                    <div className="rounded-xl border border-slate-200/80 p-3 bg-slate-50/50">
                      <span className="text-[11px] font-semibold uppercase text-slate-500">Local Calling Window</span>
                      <p className="mt-1 font-semibold text-slate-900 text-sm">11:32 AM (Permitted: 09:00 - 20:00)</p>
                      <p className="mt-0.5 text-[11px] text-slate-500">Timezone calculated from business coordinates</p>
                    </div>

                    <div className="rounded-xl border border-slate-200/80 p-3 bg-slate-50/50">
                      <span className="text-[11px] font-semibold uppercase text-slate-500">AI Mandatory Disclosure</span>
                      <p className="mt-1 font-semibold text-blue-600 text-sm">Script Enforced in First 5 Seconds</p>
                      <p className="mt-0.5 text-[11px] text-slate-500">Voice agent mandates speech opening clause</p>
                    </div>
                  </div>

                  <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50/60 p-3 text-xs text-amber-900 flex items-start gap-2">
                    <ShieldAlert className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                    <span>
                      <strong>Fail-safe guarantee:</strong> Outside <code className="font-mono">APP_ENV=production</code>, all outbound adapters (SIP telephony, WhatsApp, email) operate strictly in <em>simulated mode</em>. Zero risk of accidental sends during onboarding.
                    </span>
                  </div>
                </div>
              </motion.div>
            )}

            {/* 03: AI Voice Agents */}
            {stage.id === "voice" && (
              <motion.div
                key="voice"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.4, ease: EASE }}
                className="grid gap-8 lg:grid-cols-12 items-center"
              >
                <div className="lg:col-span-5 space-y-5">
                  <div className="inline-flex items-center gap-2 rounded-lg bg-violet-100/70 px-3 py-1 text-xs font-semibold text-violet-800">
                    <Bot className="h-3.5 w-3.5 text-violet-600" /> Phase 5: Voice Intelligence Lab
                  </div>
                  <h3 className={`${serif.className} text-3xl font-semibold text-slate-900 sm:text-4xl`}>
                    Ultra-low latency conversations with built-in AI disclosure.
                  </h3>
                  <p className="text-slate-600 leading-relaxed text-sm sm:text-base">
                    Built on open-source foundations: <span className="font-semibold text-slate-900">Twilio</span> speech recognition, <span className="font-semibold text-slate-900">Ollama</span> for reasoning, and <span className="font-semibold text-slate-900">Twilio</span> voice for phone calls (self-hosted speech on the roadmap). Human handoff on request.
                  </p>

                  <div className="space-y-2 text-xs text-slate-600">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      <span>Always opens with honest AI disclosure (&ldquo;I&apos;m an AI calling on behalf of...&rdquo;).</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      <span>Runs on your local GPU or private cloud. Zero cost per token.</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      <span>One-click hot transfer to your sales rep if interest or hesitation peaks.</span>
                    </div>
                  </div>

                  <div className="pt-2">
                    <Link
                      href="/voice-agents"
                      className="inline-flex items-center gap-2 text-sm font-semibold text-blue-600 hover:text-blue-700"
                    >
                      Listen to voice agent benchmarks <ArrowRight className="h-4 w-4" />
                    </Link>
                  </div>
                </div>

                <div className="lg:col-span-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2">
                      <Phone className="h-4 w-4 text-emerald-600 animate-pulse" />
                      <span className="font-semibold text-slate-900 text-sm">Active Twilio Telephony</span>
                    </div>
                    <button
                      onClick={() => setIsPlayingVoice(!isPlayingVoice)}
                      className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 transition-all"
                    >
                      {isPlayingVoice ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                      <span>{isPlayingVoice ? "Pause Simulation" : "Play Voice Demo"}</span>
                    </button>
                  </div>

                  {/* Audio Waveform Console */}
                  <div className="mt-4 rounded-xl bg-slate-950 p-4 text-white">
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span className="flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
                        Live WebRTC Audio Channel • 24,000 Hz
                      </span>
                      <span className="font-mono text-emerald-400">Turnaround: 410ms</span>
                    </div>

                    <div className="mt-4 flex h-14 items-center justify-center gap-1">
                      {Array.from({ length: 36 }).map((_, i) => (
                        <span
                          key={i}
                          className="w-1.5 rounded-full bg-gradient-to-t from-blue-500 via-indigo-400 to-emerald-400 transition-all duration-200"
                          style={{
                            height: isPlayingVoice
                              ? `${15 + Math.abs(Math.sin((i + Date.now() / 150) * 0.4)) * 75}%`
                              : `${20 + ((i * 23) % 40)}%`,
                          }}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Live Streaming Transcript */}
                  <div className="mt-4 space-y-2.5 rounded-xl border border-slate-100 bg-slate-50 p-3.5 text-xs">
                    <div className="flex items-start gap-2">
                      <span className="rounded-md bg-blue-600 px-1.5 py-0.5 text-[10px] font-bold text-white shrink-0">
                        AI Agent
                      </span>
                      <p className="text-slate-700 leading-relaxed">
                        &ldquo;Hi, this is an automated AI assistant calling on behalf of Studio Arc. We noticed your studio has 128 five-star reviews on Google Maps in Koregaon Park but doesn&apos;t have an online showcase for new clients. We built an instant website preview for your studio—may I text you the link?&rdquo;
                      </p>
                    </div>

                    <div className="flex items-start gap-2">
                      <span className="rounded-md bg-slate-800 px-1.5 py-0.5 text-[10px] font-bold text-white shrink-0">
                        Prospect
                      </span>
                      <p className="text-slate-900 leading-relaxed font-medium">
                        &ldquo;Oh, that&apos;s interesting. Yes, you can send it over WhatsApp to this number.&rdquo;
                      </p>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                    <span className="flex items-center gap-1 text-emerald-600 font-semibold">
                      <CheckCircle2 className="h-3.5 w-3.5" /> Intent: Meeting link agreed
                    </span>
                    <span>Sentiment Score: 94% Positive</span>
                  </div>
                </div>
              </motion.div>
            )}

            {/* 04: Instant Website Studio */}
            {stage.id === "website" && (
              <motion.div
                key="website"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.4, ease: EASE }}
                className="grid gap-8 lg:grid-cols-12 items-center"
              >
                <div className="lg:col-span-5 space-y-5">
                  <div className="inline-flex items-center gap-2 rounded-lg bg-indigo-100/70 px-3 py-1 text-xs font-semibold text-indigo-800">
                    <Globe2 className="h-3.5 w-3.5 text-indigo-600" /> Phase 6: Website Studio
                  </div>
                  <h3 className={`${serif.className} text-3xl font-semibold text-slate-900 sm:text-4xl`}>
                    Show proof before the pitch. Generated in seconds.
                  </h3>
                  <p className="text-slate-600 leading-relaxed text-sm sm:text-base">
                    Instead of generic cold calls, Leadex generates a complete, mobile-responsive, industry-tuned website preview stored on SeaweedFS S3. Showing business owners what their digital presence could look like converts cold prospects into eager clients.
                  </p>

                  {/* Vertical industry switcher */}
                  <div className="flex flex-wrap gap-2">
                    {[
                      { id: "architecture", label: "Architecture Studio" },
                      { id: "realestate", label: "Luxury Real Estate" },
                      { id: "dining", label: "Fine Dining" },
                      { id: "dental", label: "Dental Practice" },
                    ].map((item) => (
                      <button
                        key={item.id}
                        onClick={() => setSelectedIndustry(item.id as any)}
                        className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition-all ${selectedIndustry === item.id
                            ? "bg-indigo-600 text-white shadow-sm"
                            : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-100"
                          }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>

                  <div className="flex items-center gap-2 text-xs text-slate-500">
                    <span>Preview Viewport:</span>
                    <button
                      onClick={() => setDeviceViewport("desktop")}
                      className={`rounded-md px-2 py-0.5 font-medium ${deviceViewport === "desktop" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"}`}
                    >
                      Desktop
                    </button>
                    <button
                      onClick={() => setDeviceViewport("mobile")}
                      className={`rounded-md px-2 py-0.5 font-medium ${deviceViewport === "mobile" ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-700"}`}
                    >
                      Mobile (375px)
                    </button>
                  </div>
                </div>

                <div className="lg:col-span-7 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  {/* Browser chrome header */}
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2">
                      <span className="h-3 w-3 rounded-full bg-rose-400" />
                      <span className="h-3 w-3 rounded-full bg-amber-400" />
                      <span className="h-3 w-3 rounded-full bg-emerald-400" />
                      <span className="ml-2 font-mono text-xs text-slate-400">
                        https://preview.leadex.app/{selectedIndustry}-showcase
                      </span>
                    </div>
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700">
                      Generated in 1.4s
                    </span>
                  </div>

                  {/* Dynamic Realistic Website Preview */}
                  <div className="mt-4 flex justify-center overflow-hidden rounded-xl border border-slate-200 bg-slate-900">
                    <div
                      className={`transition-all duration-500 overflow-hidden ${deviceViewport === "mobile" ? "w-[320px] rounded-2xl border-4 border-slate-800 my-2" : "w-full"
                        }`}
                    >
                      <div className="relative h-64 sm:h-72 w-full overflow-hidden">
                        <img
                          src={
                            selectedIndustry === "architecture"
                              ? "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=1200&q=80"
                              : selectedIndustry === "realestate"
                                ? "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80"
                                : selectedIndustry === "dining"
                                  ? "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80"
                                  : "https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=1200&q=80"
                          }
                          alt="Industry Website Showcase"
                          className="h-full w-full object-cover transition-transform duration-700 hover:scale-105"
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/40 to-transparent p-5 flex flex-col justify-end text-white">
                          <span className="rounded-full bg-blue-500/80 backdrop-blur-md px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider w-max">
                            {selectedIndustry === "architecture"
                              ? "Modern Architectural Showcase"
                              : selectedIndustry === "realestate"
                                ? "Luxury Estates & Villas"
                                : selectedIndustry === "dining"
                                  ? "Artisanal Culinary Portfolio"
                                  : "Specialized Clinic & Care"}
                          </span>
                          <h4 className="mt-2 text-xl font-bold tracking-tight">
                            {selectedIndustry === "architecture"
                              ? "Studio Arc Interior Design"
                              : selectedIndustry === "realestate"
                                ? "Apex Prime Realty Advisors"
                                : selectedIndustry === "dining"
                                  ? "Solarium Botanical Lounge"
                                  : "Apex Center for Dental Excellence"}
                          </h4>
                          <p className="mt-1 text-xs text-slate-300 line-clamp-2">
                            Verified contact info, customer testimonials, and interactive project inquiry booking.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                    <span>11 Production Templates • Custom domain mapping available</span>
                    <button className="font-semibold text-indigo-600 hover:text-indigo-700">
                      Publish to client domain →
                    </button>
                  </div>
                </div>
              </motion.div>
            )}

            {/* 05: 17-Stage CRM Pipeline */}
            {stage.id === "crm" && (
              <motion.div
                key="crm"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.4, ease: EASE }}
                className="grid gap-8 lg:grid-cols-12 items-center"
              >
                <div className="lg:col-span-5 space-y-5">
                  <div className="inline-flex items-center gap-2 rounded-lg bg-blue-100/70 px-3 py-1 text-xs font-semibold text-blue-800">
                    <Layers className="h-3.5 w-3.5 text-blue-600" /> Phase 2: CRM & Tenancy Core
                  </div>
                  <h3 className={`${serif.className} text-3xl font-semibold text-slate-900 sm:text-4xl`}>
                    17 tracked stages with strict PostgreSQL RLS isolation.
                  </h3>
                  <p className="text-slate-600 leading-relaxed text-sm sm:text-base">
                    Every lead moves through a rigorous, auditable lifecycle from discovery to settlement. PostgreSQL Row-Level Security ensures that tenant data is never commingled or visible across organizations.
                  </p>

                  <div className="space-y-2 text-xs text-slate-600">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      <span>PostgreSQL RLS with <code className="font-mono text-slate-800">app.current_org</code> session settings.</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      <span>Full activity timeline: Notes, tasks, calls, transcripts, recordings.</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      <span>Append-only <code className="font-mono text-slate-800">audit_logs</code> for enterprise compliance.</span>
                    </div>
                  </div>
                </div>

                <div className="lg:col-span-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <span className="font-semibold text-slate-900 text-sm">Lead Lifecycle Pipeline: Studio Arc</span>
                    <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-bold text-blue-700">
                      Progress: Stage 9 of 17
                    </span>
                  </div>

                  {/* Horizontal Stage Progress Stepper */}
                  <div className="mt-4 flex items-center justify-between gap-1 overflow-x-auto pb-2">
                    {[
                      { s: "Discovered", done: true },
                      { s: "Enriched", done: true },
                      { s: "Consent Gate", done: true },
                      { s: "Voice Qualified", done: true },
                      { s: "Preview Delivered", done: true, current: true },
                      { s: "Demo Scheduled", done: false },
                      { s: "Closed Won", done: false },
                    ].map((step, i) => (
                      <div key={step.s} className="flex items-center gap-1 shrink-0">
                        <div
                          className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-semibold ${step.current
                              ? "bg-blue-600 text-white shadow-sm"
                              : step.done
                                ? "bg-emerald-50 text-emerald-700"
                                : "bg-slate-100 text-slate-400"
                            }`}
                        >
                          {step.done ? <CheckCircle2 className="h-3 w-3" /> : <span>{i + 1}</span>}
                          <span>{step.s}</span>
                        </div>
                        {i < 6 && <ChevronRight className="h-3 w-3 text-slate-300" />}
                      </div>
                    ))}
                  </div>

                  {/* Lead Card Detail */}
                  <div className="mt-4 rounded-xl border border-slate-200/80 p-4 bg-slate-50/40">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-bold text-slate-900 text-sm">Studio Arc Interior Design</h4>
                        <p className="text-xs text-slate-500">Owner: Amit Patel • Contact: +91 98201 44xxx</p>
                      </div>
                      <span className="text-right">
                        <span className="font-bold text-slate-900 text-base">₹45,000</span>
                        <p className="text-[10px] text-slate-400">Projected Retainer</p>
                      </span>
                    </div>

                    <div className="mt-3 border-t border-slate-200/60 pt-2.5 space-y-1.5 text-xs text-slate-600">
                      <div className="flex items-center gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        <span><strong>10:18 AM:</strong> AI Voice Agent completed qualification (00:48 duration).</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
                        <span><strong>10:19 AM:</strong> WhatsApp preview link sent via official Cloud API.</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-purple-500" />
                        <span><strong>10:22 AM:</strong> Preview opened by client (3 page views).</span>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* 06: Referral Marketplace */}
            {stage.id === "marketplace" && (
              <motion.div
                key="marketplace"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.4, ease: EASE }}
                className="grid gap-8 lg:grid-cols-12 items-center"
              >
                <div className="lg:col-span-5 space-y-5">
                  <div className="inline-flex items-center gap-2 rounded-lg bg-amber-100/70 px-3 py-1 text-xs font-semibold text-amber-900">
                    <Handshake className="h-3.5 w-3.5 text-amber-700" /> Phase 8: Marketplace & Commissions
                  </div>
                  <h3 className={`${serif.className} text-3xl font-semibold text-slate-900 sm:text-4xl`}>
                    Match customer needs to verified providers. Track commissions.
                  </h3>
                  <p className="text-slate-600 leading-relaxed text-sm sm:text-base">
                    Turn customer requirements into recurring revenue. When a lead needs specialized services (e.g. architects, general contractors, commercial brokers), match them through the verified marketplace and track commission settlements automatically.
                  </p>

                  <div className="space-y-2 text-xs text-slate-600">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      <span>Verified service provider credentials and licensing documents.</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      <span>Clear commission agreements with automated milestone settlements.</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      <span>Stripe & Razorpay payment adapter support.</span>
                    </div>
                  </div>
                </div>

                <div className="lg:col-span-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <span className="font-semibold text-slate-900 text-sm">Client Requirement Matching Ledger</span>
                    <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-bold text-indigo-700">
                      Match Confidence: 98%
                    </span>
                  </div>

                  <div className="mt-4 rounded-xl border border-indigo-200/80 bg-indigo-50/40 p-3.5">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-700">Client Requirement</span>
                    <h4 className="mt-1 font-bold text-slate-900 text-sm">Luxury 4BHK Penthouse Full Interior Architecture</h4>
                    <p className="mt-0.5 text-xs text-slate-600">Location: Kalyani Nagar, Pune • Budget: ₹85 Lakhs ($102,000)</p>
                  </div>

                  <div className="mt-3 space-y-2.5">
                    <div className="flex items-center justify-between rounded-xl border border-slate-200 p-3 bg-white">
                      <div className="flex items-center gap-3">
                        <div className="h-9 w-9 rounded-lg bg-blue-100 flex items-center justify-center font-bold text-blue-700 text-xs">
                          SA
                        </div>
                        <div>
                          <p className="font-semibold text-slate-900 text-sm">Studio Arc Interior Design</p>
                          <p className="text-xs text-slate-500">Verified Architectural Partner • 4.9 ★ Rating</p>
                        </div>
                      </div>
                      <span className="rounded-md bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-800">
                        Commission: 2.5% (₹2,12,500)
                      </span>
                    </div>

                    <div className="flex items-center justify-between rounded-xl border border-slate-200 p-3 bg-white">
                      <div className="flex items-center gap-3">
                        <div className="h-9 w-9 rounded-lg bg-emerald-100 flex items-center justify-center font-bold text-emerald-700 text-xs">
                          VB
                        </div>
                        <div>
                          <p className="font-semibold text-slate-900 text-sm">Vertex Builders & Contractors</p>
                          <p className="text-xs text-slate-500">Verified General Contractor • Grade-A Licensed</p>
                        </div>
                      </div>
                      <span className="rounded-md bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-800">
                        Commission: 2.0% (₹1,70,000)
                      </span>
                    </div>
                  </div>

                  <div className="mt-4 rounded-xl bg-slate-50 p-3 text-xs text-slate-600 flex justify-between items-center">
                    <span>Settlement Status: Escrow Agreement Signed</span>
                    <span className="font-bold text-slate-900">Total Referral Value: ₹3,82,500</span>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}