"use client";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  ArrowRight, BarChart3, BookOpen, Bot, CalendarCheck, Check, Code2, FileCheck2, Filter, Globe2, Handshake, KeyRound, Languages,
  Layers, LayoutTemplate, Mail, MapPin, MessageSquare, Mic, Palette, PhoneForwarded, Rocket, Scale, Search, ShieldCheck,
  Sparkles, UserCheck, Users, Wallet, Workflow,
} from "lucide-react";
import { FinalCTA } from "@/components/landing";
import { FeatureGrid, Note, PageHero, StepList } from "./page-kit";
import { CTA, Counter, Reveal, SectionHead, Tilt, WordReveal } from "./motion";
import { IndustryCarousel, INDUSTRIES } from "./industries";
import { ScrollStory } from "./story";

export function ProductPage() {
  return (
    <>
      <PageHero eyebrow="Product" title="One platform, from discovery to deal." body="Leadex combines business discovery, a lead CRM, AI voice agents, outreach, website generation, workflows, a referral marketplace and analytics in one workspace." visual="funnel" />
      <FeatureGrid eyebrow="Modules" title="Every stage, connected." items={[
        { icon: Search, title: "Business Discovery", body: "Search by country, city, locality and industry with source tracking on every field." },
        { icon: Users, title: "Lead CRM", body: "17 pipeline stages, scoring, ownership, tasks, notes and a full timeline." },
        { icon: Bot, title: "AI Voice Agents", body: "Template-based agents for qualification, booking and follow-up." },
        { icon: Mail, title: "Email & WhatsApp", body: "Approval-gated outreach via Gmail, Outlook and the WhatsApp Business Platform." },
        { icon: Globe2, title: "Website Studio", body: "Industry-specific website previews generated from verified details." },
        { icon: Handshake, title: "Referral Marketplace", body: "Match requirements to verified providers and track commissions." },
        { icon: Workflow, title: "Workflows", body: "Conditions, approvals, retries and execution history." },
        { icon: BarChart3, title: "Analytics", body: "Funnels and performance computed only from recorded activity." },
        { icon: ShieldCheck, title: "Compliance", body: "Consent, suppression lists and jurisdiction-aware rules built in." },
      ]} />
      <section className="py-10"><div className="px-4 sm:px-6"><SectionHead eyebrow="See it move" title="Follow a lead through Leadex." /></div><ScrollStory /></section>
      <FinalCTA />
    </>
  );
}

export function VoiceAgentsPage() {
  return (
    <>
      <PageHero eyebrow="AI Voice Agents" title="Calls that qualify, book and follow up." body="Configure an agent from a template, give it your script and knowledge, and let it handle first conversations. Every call opens with an AI disclosure." visual="wave" />
      <FeatureGrid title="Built for real conversations." items={[
        { icon: LayoutTemplate, title: "9 agent templates", body: "Start from templates for qualification, appointment booking, follow-up and more." },
        { icon: Mic, title: "Natural voice", body: "Low-latency speech with interruption handling and a configurable persona." },
        { icon: Languages, title: "Languages", body: "English today, with Hindi and Telugu being evaluated." },
        { icon: PhoneForwarded, title: "Human hand-off", body: "Transfer to a person whenever the caller asks or the agent is unsure." },
        { icon: CalendarCheck, title: "Booking", body: "Agents can propose and record meeting slots against the lead." },
        { icon: ShieldCheck, title: "Disclosure and consent", body: "Calls are blocked when consent is missing; transcripts are stored with the lead." },
      ]} />
      <StepList title="How a call happens." steps={[
        { title: "Lead is approved", body: "Only leads with recorded consent and an allowed jurisdiction are eligible." },
        { title: "Agent places the call", body: "It discloses that it is an AI and follows your script." },
        { title: "Outcome is recorded", body: "Transcript, summary and next step are attached to the lead timeline." },
      ]} />
      <FinalCTA />
    </>
  );
}

export function LeadGenPage() {
  return (
    <>
      <PageHero eyebrow="Lead Generation" title="Find the businesses others miss." body="Discover businesses by region and industry, including those with no website, audit their online presence, and move them through a pipeline you can explain." visual="globe" />
      <FeatureGrid title="Discovery with provenance." items={[
        { icon: MapPin, title: "Region and industry search", body: "Country, city, locality and category filters." },
        { icon: Filter, title: "Scoring", body: "Explainable scores based on website status, fit and engagement." },
        { icon: FileCheck2, title: "Source tracking", body: "Each data point records where it came from and when." },
        { icon: UserCheck, title: "Contact verification", body: "Verify before outreach; unverified contacts stay blocked." },
        { icon: Layers, title: "17 lead stages", body: "From discovered to converted, with ownership and tasks." },
        { icon: Scale, title: "6 jurisdictions", body: "Country-aware compliance rules decide what outreach is allowed." },
      ]} />
      <FinalCTA />
    </>
  );
}

export function WebsiteStudioPage() {
  return (
    <>
      <PageHero eyebrow="Website Studio" title="Show them their website before you pitch." body="Generate a responsive, industry-specific website preview from verified business details, edit it, and share a link." visual="browser" />
      <FeatureGrid title="From details to a live preview." items={[
        { icon: LayoutTemplate, title: "11 website templates", body: "Designs tuned for different industries." },
        { icon: Sparkles, title: "AI copy", body: "Draft headlines and sections from verified information only." },
        { icon: Palette, title: "Editable", body: "Adjust colours, sections and content before sharing." },
        { icon: Rocket, title: "Share and publish", body: "Send a preview link with outreach, then publish when they agree." },
      ]} />
      <FinalCTA />
    </>
  );
}

export function MarketplacePage() {
  return (
    <>
      <PageHero eyebrow="Referral Marketplace" title="Turn requirements into commissioned referrals." body="Capture what a customer needs, match it with verified providers, and track the referral from introduction to settlement." visual="network" />
      <StepList title="How referrals flow." steps={[
        { title: "Capture the requirement", body: "Budget, location, timeline and scope are recorded with consent." },
        { title: "Match verified providers", body: "Architects, builders, brokers and contractors who have been verified." },
        { title: "Introduce and track", body: "Every status change is logged on the referral." },
        { title: "Settle the commission", body: "Commission terms and settlement status are tracked per referral." },
      ]} />
      <FeatureGrid title="Built on trust." items={[
        { icon: UserCheck, title: "Provider verification", body: "Only verified providers receive referrals." },
        { icon: Wallet, title: "Commission tracking", body: "Agreed terms, invoices and settlement in one place." },
        { icon: ShieldCheck, title: "Consent first", body: "Customer details are shared only with permission." },
      ]} />
      <FinalCTA />
    </>
  );
}

export function IndustriesPage() {
  return (
    <>
      <PageHero eyebrow="Industries" title="Tuned for the businesses you serve." body="Agent scripts, website templates and discovery filters for local and service industries." />
      <IndustryCarousel />
      <section className="px-4 py-20 sm:px-6">
        <div className="mx-auto grid max-w-6xl gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {INDUSTRIES.map(({ icon: Icon, name, body, tint }, i) => (
            <Reveal key={name} i={i % 3}>
              <Tilt className="h-full rounded-3xl" max={6}>
                <div className="h-full rounded-3xl border border-line bg-white p-7 shadow-card">
                  <div className={`grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br ${tint} text-white`}><Icon className="h-5 w-5" /></div>
                  <h2 className="mt-5 text-lg font-semibold">{name}</h2>
                  <p className="mt-2 text-[15px] text-muted">{body}</p>
                </div>
              </Tilt>
            </Reveal>
          ))}
        </div>
      </section>
      <FinalCTA />
    </>
  );
}

export function DocsPage() {
  const sections = [
    { icon: Rocket, t: "Getting started", b: "Create a workspace, invite your team and run your first discovery search.", href: "/register" },
    { icon: Search, t: "Discovery and leads", b: "How search, scoring, stages and source tracking work.", href: "/lead-generation" },
    { icon: Bot, t: "Voice agents", b: "Templates, scripts, disclosure and hand-off.", href: "/voice-agents" },
    { icon: Globe2, t: "Website Studio", b: "Templates, editing and sharing previews.", href: "/website-studio" },
    { icon: Handshake, t: "Marketplace", b: "Requirements, provider verification and commissions.", href: "/marketplace-info" },
    { icon: KeyRound, t: "Integrations", b: "Connect email, WhatsApp and telephony from your workspace settings after sign-in.", href: "/login" },
  ];
  return (
    <>
      <PageHero eyebrow="Docs" title="Learn how Leadex works." body="Guides for every module. Full developer and API documentation is coming soon." />
      <section className="px-4 pb-24 sm:px-6">
        <div className="mx-auto grid max-w-6xl gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {sections.map(({ icon: Icon, t, b, href }, i) => (
            <Reveal key={t} i={i % 3}>
              <motion.div whileHover={{ y: -6 }} whileTap={{ scale: 0.97 }}>
                <Link href={href} className="group block h-full rounded-3xl border border-line bg-white p-7 shadow-card hover:shadow-lift">
                  <Icon className="h-6 w-6 text-accent" />
                  <h2 className="mt-4 text-lg font-semibold">{t}</h2>
                  <p className="mt-2 text-[15px] text-muted">{b}</p>
                  <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-accent">Open <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" /></span>
                </Link>
              </motion.div>
            </Reveal>
          ))}
          <Reveal i={0} className="sm:col-span-2 lg:col-span-3">
            <div className="flex items-center gap-4 rounded-3xl border border-dashed border-line bg-raised p-7 text-muted">
              <Code2 className="h-6 w-6 shrink-0" /><BookOpen className="h-6 w-6 shrink-0" />
              <p>API reference and webhooks documentation: coming soon.</p>
            </div>
          </Reveal>
        </div>
      </section>
    </>
  );
}
