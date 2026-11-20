"use client";
import Link from "next/link";
import { useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight, Briefcase, Building2, CheckCircle2, ChevronRight, Globe2, Hammer,
  Home, PenTool, Phone, Sparkles, Stethoscope, Store, UtensilsCrossed, Users
} from "lucide-react";
import { serif } from "./fonts";

const VERTICALS = [
  {
    id: "architecture",
    title: "Architecture & Interior Design",
    headline: "Showcase bespoke portfolios before asking for the consultation.",
    desc: "Discover studios with outdated web presences. Generate high-aesthetic portfolio previews featuring residential villas and hospitality projects, then route client leads to verified contractors.",
    image: "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=800&q=80",
    metrics: "4.8x higher booking rate with live portfolio previews",
    tag: "Design & Construction",
    features: [
      "Auto-generates project portfolio gallery from Google Maps reviews",
      "Qualifies budget and timeline via natural AI voice",
      "Direct integration with Referral Marketplace for builders",
    ],
  },
  {
    id: "realestate",
    title: "Luxury Real Estate & Brokers",
    headline: "Match high-net-worth property requirements to verified local brokers.",
    desc: "Scan local markets for independent agencies lacking modern listing portals. Deploy AI voice agents to pre-qualify buyer budgets and match them to verified property portfolios.",
    image: "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=800&q=80",
    metrics: "$140,000+ in referral commissions settled across networks",
    tag: "Commercial & Luxury",
    features: [
      "Property requirement matching engine with escrow agreements",
      "Automated WhatsApp virtual tour links via official Cloud API",
      "Strict compliance with national DNC and calling hours",
    ],
  },
  {
    id: "construction",
    title: "General Contractors & Builders",
    headline: "Turn raw renovation briefs into signed construction contracts.",
    desc: "Locate regional trades, electrical, plumbing, and structural contractors. Give them ready-to-deploy quote landing pages and match them to inbound architectural projects.",
    image: "https://images.unsplash.com/photo-1541888946425-d0fbb18086f6?auto=format&fit=crop&w=800&q=80",
    metrics: "64% reduction in manual quote follow-up time",
    tag: "Contracting & Trades",
    features: [
      "Instant quick-estimate website templates",
      "Automated milestone tracking & payment settlement",
      "Licensing and insurance document verification",
    ],
  },
  {
    id: "hospitality",
    title: "Artisanal Restaurants & Hospitality",
    headline: "Convert local diners with menu-first previews & reservation agents.",
    desc: "Discover bistros, lounges, and fine-dining spots that depend solely on walk-ins. Generate fast-loading mobile menu previews and deploy AI reservation voice assistants.",
    image: "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=800&q=80",
    metrics: "3.2x more private event & group table inquiries",
    tag: "Dining & Events",
    features: [
      "Interactive menu display and table reservation forms",
      "AI telephone agent for after-hours reservation bookings",
      "Google Maps rating and review showcase widget",
    ],
  },
  {
    id: "healthcare",
    title: "Specialized Clinics & Practices",
    headline: "Strict consent-first appointment outreach for medical practices.",
    desc: "Equip dental studios, physiotherapy centers, and specialty clinics with consent-gated appointment scheduling agents that adhere strictly to DPDP, HIPAA, and TRAI standards.",
    image: "https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=800&q=80",
    metrics: "100% compliance record with zero DNC regulatory flags",
    tag: "Healthcare & Wellness",
    features: [
      "Automated patient appointment confirmation & reminders",
      "Mandatory AI disclosure on all telephone interactions",
      "Encrypted patient records with PostgreSQL Row-Level Security",
    ],
  },
  {
    id: "professional",
    title: "Agencies & Professional Services",
    headline: "Transform cold prospects into credibility-backed enterprise accounts.",
    desc: "Consultants, legal practices, and marketing agencies use Leadex to generate custom audit microsites showing prospects exactly where their digital growth is bottlenecked.",
    image: "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=800&q=80",
    metrics: "85% higher conversion over generic cold emails",
    tag: "B2B & Legal",
    features: [
      "Automated website audit scoring (SEO, speed, accessibility)",
      "Multi-channel sequences across Gmail, Outlook & WhatsApp",
      "Multi-tenant workspace isolation for agency client rosters",
    ],
  },
];

export function IndustrySolutions() {
  const [selectedVertical, setSelectedVertical] = useState(0);
  const current = VERTICALS[selectedVertical];

  return (
    <section id="industries" className="relative scroll-mt-20 overflow-hidden bg-white py-24 sm:py-32">
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6">
        <div className="mx-auto max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50/70 px-4 py-1 text-xs font-semibold text-blue-700">
            <Building2 className="h-3.5 w-3.5 text-blue-600" /> Industry Playbooks
          </div>
          <h2 className={`${serif.className} mt-4 text-[38px] leading-[1.08] tracking-tight text-slate-900 sm:text-[56px]`}>
            Tailored for businesses <br className="hidden sm:inline" />
            <span className="italic text-blue-600">that build and serve.</span>
          </h2>
          <p className="mt-4 text-base leading-relaxed text-slate-600 sm:text-lg">
            Every vertical has unique compliance boundaries, prospect expectations, and sales lifecycles. Leadex ships pre-tuned prompts, templates, and workflows for each.
          </p>
        </div>

        {/* Vertical Selector Buttons */}
        <div className="mt-12 flex flex-wrap justify-center gap-2">
          {VERTICALS.map((item, index) => {
            const active = selectedVertical === index;
            return (
              <button
                key={item.id}
                onClick={() => setSelectedVertical(index)}
                className={`rounded-full px-4 py-2 text-xs font-semibold transition-all ${active
                    ? "bg-slate-900 text-white shadow-md"
                    : "border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:bg-slate-50"
                  }`}
              >
                {item.title}
              </button>
            );
          })}
        </div>

        {/* Hero Solution Card with Real Photography */}
        <div className="mt-10 overflow-hidden rounded-3xl border border-slate-200/90 bg-slate-50/50 p-6 shadow-[0_20px_50px_rgba(15,23,42,0.06)] sm:p-10">
          <div className="grid gap-10 lg:grid-cols-12 items-center">
            {/* Left 6 cols: Realistic Curated Photography */}
            <div className="lg:col-span-6 relative overflow-hidden rounded-2xl border border-slate-200/80 bg-slate-900 shadow-md">
              <div className="relative h-72 sm:h-96 w-full overflow-hidden">
                <img loading="lazy" decoding="async"
                  src={current.image}
                  alt={current.title}
                  className="h-full w-full object-cover transition-transform duration-700 hover:scale-105"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent p-6 flex flex-col justify-end text-white">
                  <span className="rounded-full bg-blue-600/90 backdrop-blur-md px-3 py-1 text-xs font-semibold uppercase tracking-wider w-max">
                    {current.tag}
                  </span>
                  <p className="mt-2 text-base sm:text-lg font-bold text-white leading-tight">
                    {current.metrics}
                  </p>
                </div>
              </div>
            </div>

            {/* Right 6 cols: Solution Overview */}
            <div className="lg:col-span-6 space-y-6">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-blue-600">Specialized Workflow</span>
                <h3 className={`${serif.className} mt-2 text-3xl font-bold text-slate-900 sm:text-4xl leading-tight`}>
                  {current.headline}
                </h3>
                <p className="mt-4 text-slate-600 leading-relaxed text-sm sm:text-base">
                  {current.desc}
                </p>
              </div>

              <div className="space-y-3 pt-2">
                {current.features.map((feat) => (
                  <div key={feat} className="flex items-start gap-2.5">
                    <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
                    <span className="text-sm font-medium text-slate-700">{feat}</span>
                  </div>
                ))}
              </div>

              <div className="pt-4 flex items-center gap-4">
                <Link
                  href="/register"
                  className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-6 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 transition-all"
                >
                  <span>Deploy {current.title} Playbook</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}