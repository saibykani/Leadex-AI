"use client";
import Link from "next/link";
import {
  ArrowRight, BarChart3, Bot, Globe2, Handshake, Mail, Search, Sparkles, Users, Workflow
} from "lucide-react";
import { MarketingShell } from "@/components/marketing/chrome";
import { Reveal, ScrollText, SectionHead, Tilt } from "@/components/marketing/motion";
import { BuiltFor, Integrations, PricingTeaser, TalkToSales, WhyNow } from "@/components/marketing/cinema";
import { serif } from "@/components/marketing/fonts";
import { INDUSTRIES } from "@/components/marketing/industries";

import { LuminousHero } from "@/components/marketing/luminous-hero";
import dynamic from "next/dynamic";

// Below-the-fold sections are split into their own chunks so the hero paints first.
const lazy = (h: number) => () => <div style={{ minHeight: h }} aria-hidden />;
const InteractivePlatformTour = dynamic(() => import("@/components/marketing/interactive-platform-tour").then((m) => m.InteractivePlatformTour), { loading: lazy(900) });
const VisualWorkflowBuilder = dynamic(() => import("@/components/marketing/visual-workflow-builder").then((m) => m.VisualWorkflowBuilder), { loading: lazy(800) });
const IndustrySolutions = dynamic(() => import("@/components/marketing/industry-solutions").then((m) => m.IndustrySolutions), { loading: lazy(800) });
const DeepArchitecture = dynamic(() => import("@/components/marketing/deep-architecture").then((m) => m.DeepArchitecture), { loading: lazy(800) });
const TestimonialsAndFaq = dynamic(() => import("@/components/marketing/testimonials-and-faq").then((m) => m.TestimonialsAndFaq), { loading: lazy(600) });

const MODULES = [
  { icon: Search, title: "Business Discovery", href: "/lead-generation", body: "Find businesses by country, city, locality and industry, including those without a website, with every data point traced to its source.", tint: "from-blue-600 to-sky-500" },
  { icon: Users, title: "Lead CRM", href: "/product", body: "A full pipeline from discovered to converted, with 17 tracked stages, notes, tasks, ownership and PostgreSQL Row-Level Security.", tint: "from-indigo-600 to-blue-600" },
  { icon: Bot, title: "AI Voice Agents", href: "/voice-agents", body: "AI voice agents (Twilio today) for qualification, booking and follow-up, with AI disclosure built in.", tint: "from-violet-600 to-purple-600" },
  { icon: Globe2, title: "Website Studio", href: "/website-studio", body: "Generate responsive, industry-specific website previews from verified business information, ready to share for approval.", tint: "from-emerald-500 to-teal-500" },
  { icon: Mail, title: "Email & WhatsApp", href: "/product", body: "Personalised, consent-gated outreach through Gmail, Outlook and the official WhatsApp Business Cloud Platform.", tint: "from-amber-500 to-orange-500" },
  { icon: Handshake, title: "Referral Marketplace", href: "/marketplace-info", body: "Match customer requirements with verified architects, builders and brokers, and track commissions to settlement.", tint: "from-rose-500 to-pink-500" },
  { icon: Workflow, title: "Workflow Automation", href: "/product", body: "Multi-step workflows with Celery task queues, condition branches, approvals, retries and execution history.", tint: "from-blue-500 to-emerald-500" },
  { icon: BarChart3, title: "Analytics & Usage", href: "/product", body: "Funnel, campaign, agent and revenue analytics built only from activity actually recorded in your workspace.", tint: "from-blue-600 to-violet-600" },
];

export function Landing() {
  return (
    <MarketingShell>
      {/* 1. Luminous Hero (Natural colors, 3D multi-layer UI, realistic photography) */}
      <LuminousHero />

      {/* 2. Marquee Ticker */}
      <BuiltFor names={INDUSTRIES.map((x) => x.name)} />

        {/* 3. Manifesto Statement with Scroll-Linked Reveal */}
        <section className="relative px-4 py-24 sm:px-6 sm:py-32 bg-white">
          <ScrollText
            className={`${serif.className} mx-auto max-w-4xl text-[32px] leading-[1.18] sm:text-[52px] text-slate-900 text-center font-normal`}
            text="Most growth tools stop at a list of names. Leadex follows the whole journey: it finds the business, checks consent, starts the conversation, shows the owner what their website could be, and records every step until the deal is done."
          />
        </section>

        {/* 4. Complete Interactive 6-Stage Platform Sandbox */}
        <InteractivePlatformTour />

          {/* 5. Autonomous Visual Workflow Builder */}
          <VisualWorkflowBuilder />

          {/* 6. Industry Solutions with High-Resolution Photography */}
          <IndustrySolutions />

          {/* 7. Product Modules Overview */}
          <section id="what-we-do" className="scroll-mt-20 px-4 py-24 sm:px-6 bg-slate-50/60">
            <SectionHead
              eyebrow="Unified Capabilities"
              title="Everything you need to grow, in one place."
              body="Every stage of business development, from first search to final commission, with AI doing the repetitive work and you staying in control."
            />
            <div className="mx-auto mt-16 grid max-w-6xl gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {MODULES.map(({ icon: Icon, title, body, tint, href }, i) => (
            <Reveal key={title} i={i % 4}>
              <Tilt className="h-full rounded-3xl">
                <Link
                  href={href}
                  className="group block h-full rounded-3xl border border-slate-200/90 bg-white p-7 shadow-sm transition-all hover:border-blue-400 hover:shadow-md"
                >
                  <div className={`grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br ${tint} text-white shadow-sm transition-transform duration-500 group-hover:scale-110`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-6 text-[18px] font-bold text-slate-900 tracking-tight">{title}</h3>
                  <p className="mt-2 text-[14px] leading-relaxed text-slate-600">{body}</p>
                  <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-blue-600">
                    Learn more <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
                  </span>
                </Link>
              </Tilt>
            </Reveal>
          ))}
        </div>
      </section>

      {/* 8. Deep Architecture & Security Pillars */ }
                < DeepArchitecture />

          {/* 9. Interactive ROI & Cost Calculator */}

          {/* 10. Social Proof Testimonials & Architecture FAQ */}
          <TestimonialsAndFaq />

          {/* 11. Integrations Grid */}
          <Integrations />

          {/* 12. Why Now */}
          <WhyNow />

          {/* 13. Transparent Pricing Teaser */}
          <PricingTeaser />

          {/* 14. Talk to Sales */}
          <TalkToSales />

          {/* 15. Final Luminous CTA */}
          <FinalLuminousCTA />
        </MarketingShell>
        );
}

export function FinalLuminousCTA() {
  return (
        <section className="px-4 py-24 sm:px-6 bg-white">
          <Reveal className="relative mx-auto max-w-6xl overflow-hidden rounded-[36px] bg-gradient-to-br from-blue-700 via-indigo-700 to-emerald-700 px-6 py-20 text-center text-white shadow-2xl">
            <div aria-hidden className="pointer-events-none absolute -right-20 -top-20 h-80 w-80 rounded-full bg-white/10 blur-2xl" />
            <div aria-hidden className="pointer-events-none absolute -bottom-20 -left-20 h-80 w-80 rounded-full bg-emerald-400/15 blur-2xl" />

                <div className="relative mx-auto max-w-3xl">
                  <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-wider text-emerald-200">
                    <Sparkles className="h-3.5 w-3.5" /> Guided onboarding
                  </span>
                  <h2 className={`${serif.className} mt-6 text-[38px] font-bold leading-tight tracking-tight sm:text-[60px]`}>
                    Ready to turn unlisted local businesses into high-value clients?
                  </h2>
                  <p className="mx-auto mt-4 max-w-xl text-base text-white/85 sm:text-lg">
                    Set up your isolated workspace in minutes.
                  </p>

                  <div className="mt-10 flex flex-wrap justify-center gap-4">
                    <Link
                      href="/register"
                      className="inline-flex h-13 items-center gap-2 rounded-full bg-white px-8 py-3.5 text-[15px] font-bold text-slate-900 shadow-lg hover:bg-slate-50 transition-all hover:scale-105"
                    >
                      <span>Get started free</span>
                      <ArrowRight className="h-4 w-4" />
                    </Link>

                    <Link
                      href="/demo-booking"
                      className="inline-flex h-13 items-center gap-2 rounded-full border border-white/30 bg-white/10 px-7 py-3.5 text-[15px] font-semibold text-white backdrop-blur-md hover:bg-white/20 transition-all"
                    >
                      <span>Book live demo</span>
                    </Link>
                  </div>

                  <p className="mt-6 text-xs text-white/60">
                    PostgreSQL RLS isolated • Consent-gated outreach • Open-source AI by default
                  </p>
                </div>
              </Reveal>
            </section>
            );
}

/** Backward-compatible name used by marketing subpages. */
export { FinalLuminousCTA as FinalCTA };
