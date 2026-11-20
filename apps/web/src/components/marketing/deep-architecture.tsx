"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import {
  CheckCircle2, Cpu, Database, Eye, FileText, KeyRound, Layers, Lock,
  Scale, Server, ShieldCheck, Terminal, Zap
} from "lucide-react";
import { serif } from "./fonts";

const ARCH_STACK = [
  {
    name: "FastAPI + Next.js",
    category: "App & Web Layer",
    desc: "Single monorepo, strict OpenAPI schema, Pydantic bound parameters, JWT + rotating refresh tokens.",
    color: "from-blue-500 to-indigo-600",
  },
  {
    name: "PostgreSQL 16 + RLS",
    category: "Data Isolation",
    desc: "Row-Level Security on every tenant table. Enforced via app.current_org session setting; non-owner role cannot bypass.",
    color: "from-emerald-500 to-teal-600",
  },
  {
    name: "Ollama (Self-Hosted)",
    category: "AI Reasoning",
    desc: "Run open-weight LLMs on local hardware or private VMs. Zero token tax. Paid cloud fallbacks strictly opt-in.",
    color: "from-violet-500 to-purple-600",
  },
  {
    name: "AI Voice Agents",
    category: "WebRTC Telephony",
    desc: "Twilio speech recognition and voice today; self-hosted LiveKit + faster-whisper + Piper pipeline on the roadmap. Global and per-agent kill switches.",
    color: "from-amber-500 to-orange-600",
  },
  {
    name: "Qdrant Vector DB",
    category: "Knowledge & RAG",
    desc: "Embedded company knowledge and search vectors with mandatory org_id payload filter and citation provenance.",
    color: "from-cyan-500 to-blue-600",
  },
  {
    name: "SeaweedFS (S3 API)",
    category: "Object Storage",
    desc: "Self-hosted S3-compatible storage for generated website previews, recordings, transcripts, and document audits.",
    color: "from-rose-500 to-pink-600",
  },
];

const SECURITY_PILLARS = [
  {
    icon: Database,
    title: "PostgreSQL Row-Level Security",
    desc: "Tenant isolation is enforced at the database level. Even if an API endpoint forgot to filter by organization_id, Postgres rejects cross-tenant queries.",
  },
  {
    icon: ShieldCheck,
    title: "Default-BLOCK OutreachGate",
    desc: "Zero calls, emails, or WhatsApp messages leave the system without verifiable lawful basis, DNC clearance, and permitted calling window checks.",
  },
  {
    icon: KeyRound,
    title: "Fernet Secret Encryption",
    desc: "Integration API credentials, OAuth tokens, and MFA secrets are encrypted with Fernet symmetric keys stored outside the database.",
  },
  {
    icon: FileText,
    title: "Append-Only Audit Logs",
    desc: "Every mutation, login, permission change, and outreach event writes an immutable audit record with actor ID, IP address, and timestamp.",
  },
  {
    icon: Cpu,
    title: "Open-Source AI Independence",
    desc: "Powered by Ollama, self-hosted on your own hardware. No vendor lock-in, no unpredictable API pricing spikes, and complete data privacy.",
  },
  {
    icon: Scale,
    title: "Universal Kill Switches",
    desc: "Global and per-tenant kill switches allow instant cessation of all outbound telephony or messaging in under 1 second.",
  },
];

export function DeepArchitecture() {
  const [activeTab, setActiveTab] = useState<"diagram" | "security">("diagram");

  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-white via-[#f8faff] to-white py-24 sm:py-32">
      {/* Background ambient lighting */}
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute top-1/3 left-1/2 h-[600px] w-[800px] -translate-x-1/2 rounded-full bg-blue-100/40 blur-[130px]" />
      </div>

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6">
        <div className="mx-auto max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50/70 px-4 py-1 text-xs font-semibold text-blue-700">
            <Server className="h-3.5 w-3.5 text-blue-600" /> System Architecture & Security
          </div>
          <h2 className={`${serif.className} mt-4 text-[38px] leading-[1.08] tracking-tight text-slate-900 sm:text-[56px]`}>
            Enterprise-grade by design, <br className="hidden sm:inline" />
            <span className="italic text-blue-600">not as an afterthought.</span>
          </h2>
          <p className="mt-4 text-base leading-relaxed text-slate-600 sm:text-lg">
            Built from day one with multi-tenant database isolation, open-source local inference, and immutable compliance logging. Verified across Phase 1 monorepo tests.
          </p>

          <div className="mt-8 flex justify-center">
            <div className="flex rounded-2xl border border-slate-200 bg-slate-100 p-1 text-xs font-semibold text-slate-600">
              <button
                onClick={() => setActiveTab("diagram")}
                className={`rounded-xl px-5 py-2 transition-all ${
                  activeTab === "diagram" ? "bg-white text-slate-900 shadow-sm" : "hover:text-slate-900"
                }`}
              >
                Monorepo Stack Topology
              </button>
              <button
                onClick={() => setActiveTab("security")}
                className={`rounded-xl px-5 py-2 transition-all ${
                  activeTab === "security" ? "bg-white text-slate-900 shadow-sm" : "hover:text-slate-900"
                }`}
              >
                6 Security Pillars
              </button>
            </div>
          </div>
        </div>

        {activeTab === "diagram" && (
          <div className="mt-14 space-y-8">
            {/* Architectural Flow Diagram Card */}
            <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white p-6 shadow-[0_20px_50px_rgba(15,23,42,0.05)] sm:p-10">
              <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                <div className="flex items-center gap-2">
                  <span className="h-3 w-3 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="font-semibold text-slate-900 text-sm">Leadex Unified Request Topology</span>
                </div>
                <span className="text-xs text-slate-500 font-mono">TLS 1.3 • Nginx Reverse Proxy</span>
              </div>

              {/* Visual Flow diagram */}
              <div className="mt-8 grid gap-4 lg:grid-cols-4 items-center">
                {/* 1. Ingress */}
                <div className="rounded-2xl border border-slate-200 bg-slate-50/60 p-5 text-center">
                  <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-blue-100 text-blue-600">
                    <Server className="h-6 w-6" />
                  </div>
                  <h4 className="mt-3 font-bold text-slate-900 text-sm">Nginx Reverse Proxy</h4>
                  <p className="mt-1 text-xs text-slate-500">Only public entry point. TLS termination & IP rate limiting.</p>
                </div>

                {/* 2. Core Service */}
                <div className="rounded-2xl border border-blue-200 bg-blue-50/40 p-5 text-center shadow-sm">
                  <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-blue-600 text-white">
                    <Cpu className="h-6 w-6" />
                  </div>
                  <h4 className="mt-3 font-bold text-slate-900 text-sm">FastAPI Application</h4>
                  <p className="mt-1 text-xs text-slate-600">
                    TenantContext dependency + RBAC permissions & OutreachGate.
                  </p>
                </div>

                {/* 3. Data Tier */}
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50/40 p-5 text-center shadow-sm">
                  <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-emerald-600 text-white">
                    <Database className="h-6 w-6" />
                  </div>
                  <h4 className="mt-3 font-bold text-slate-900 text-sm">PostgreSQL 16 RLS</h4>
                  <p className="mt-1 text-xs text-slate-600">
                    Strict Row-Level Security with app.current_org session setting.
                  </p>
                </div>

                {/* 4. AI & Media Tier */}
                <div className="rounded-2xl border border-purple-200 bg-purple-50/40 p-5 text-center shadow-sm">
                  <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-purple-600 text-white">
                    <Zap className="h-6 w-6" />
                  </div>
                  <h4 className="mt-3 font-bold text-slate-900 text-sm">Ollama + Qdrant</h4>
                  <p className="mt-1 text-xs text-slate-600">
                    Self-hosted open-weight LLMs, vector search & SeaweedFS S3 previews.
                  </p>
                </div>
              </div>
            </div>

            {/* 6 Technology Modules */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {ARCH_STACK.map((item) => (
                <div
                  key={item.name}
                  className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:border-blue-400 hover:shadow-md"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900 text-sm">{item.name}</span>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                      {item.category}
                    </span>
                  </div>
                  <p className="mt-2.5 text-xs text-slate-600 leading-relaxed">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "security" && (
          <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {SECURITY_PILLARS.map((p) => {
              const Icon = p.icon;
              return (
                <div
                  key={p.title}
                  className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition-all hover:border-emerald-300 hover:shadow-md"
                >
                  <div className="grid h-11 w-11 place-items-center rounded-xl bg-emerald-100 text-emerald-700">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h4 className="mt-4 font-bold text-slate-900 text-base">{p.title}</h4>
                  <p className="mt-2 text-xs leading-relaxed text-slate-600">{p.desc}</p>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}

