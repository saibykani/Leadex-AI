"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight, Bot, Check, CheckCircle2, ChevronRight, Clock, Code, Cpu, Database,
  FileCheck, GitBranch, Globe2, Layers, MessageSquare, Phone, Play, RefreshCw,
  ShieldCheck, Sparkles, UserCheck, Zap
} from "lucide-react";
import { serif } from "./fonts";

const WORKFLOW_NODES = [
  {
    id: "trigger",
    type: "Trigger",
    title: "New Discovery Batch",
    desc: "Google Places API finds 25 local businesses lacking websites",
    icon: Database,
    color: "from-blue-500 to-indigo-600",
    badge: "Celery Task",
  },
  {
    id: "compliance",
    type: "Rule",
    title: "OutreachGate Verification",
    desc: "DNC registry check, lawful basis check & calling window audit",
    icon: ShieldCheck,
    color: "from-emerald-500 to-teal-600",
    badge: "Zero Violations",
  },
  {
    id: "website",
    type: "AI Action",
    title: "Website Studio Gen",
    desc: "Autonomous generation of mobile-responsive portfolio preview",
    icon: Globe2,
    color: "from-indigo-500 to-violet-600",
    badge: "SeaweedFS S3",
  },
  {
    id: "voice",
    type: "Voice Action",
    title: "AI Agent Qualification",
    desc: "Outreach call with AI disclosure & calendar demo scheduling",
    icon: Phone,
    color: "from-violet-500 to-purple-600",
    badge: "AI disclosure first",
  },
  {
    id: "crm",
    type: "CRM Output",
    title: "Advance to Active Deal",
    desc: "Log recording & transcript, assign account rep, notify Slack",
    icon: UserCheck,
    color: "from-amber-500 to-rose-600",
    badge: "Postgres RLS",
  },
];

export function VisualWorkflowBuilder() {
  const [isRunning, setIsRunning] = useState(false);
  const [activeStep, setActiveStep] = useState(2);

  function simulateRun() {
    setIsRunning(true);
    setActiveStep(0);
    const interval = setInterval(() => {
      setActiveStep((prev) => {
        if (prev >= WORKFLOW_NODES.length - 1) {
          clearInterval(interval);
          setIsRunning(false);
          return WORKFLOW_NODES.length - 1;
        }
        return prev + 1;
      });
    }, 900);
  }

  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-[#f4f7fc] via-white to-white py-24 sm:py-32">
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6">
        <div className="mx-auto max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50/70 px-4 py-1 text-xs font-semibold text-indigo-700">
            <Cpu className="h-3.5 w-3.5 text-indigo-600" /> Phase 9: Workflow Automation Engine
          </div>
          <h2 className={`${serif.className} mt-4 text-[38px] leading-[1.08] tracking-tight text-slate-900 sm:text-[56px]`}>
            Autonomous multi-step execution. <br className="hidden sm:inline" />
            <span className="italic text-indigo-600">With human approvals when it matters.</span>
          </h2>
          <p className="mt-4 text-base leading-relaxed text-slate-600 sm:text-lg">
            Powered by Celery task workers and PostgreSQL idempotency keys. Chain discovery, audits, voice qualification, and preview distribution into resilient, self-healing pipelines.
          </p>

          <div className="mt-8 flex justify-center">
            <button
              onClick={simulateRun}
              disabled={isRunning}
              className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-6 py-2.5 text-xs font-semibold text-white shadow-md hover:bg-slate-800 transition-all disabled:opacity-60"
            >
              <Play className={`h-3.5 w-3.5 fill-current ${isRunning ? "animate-spin" : ""}`} />
              <span>{isRunning ? "Executing Pipeline..." : "Simulate Automated Workflow Run"}</span>
            </button>
          </div>
        </div>

        {/* Visual Node Diagram Flow */}
        <div className="mt-16 overflow-hidden rounded-3xl border border-slate-200/90 bg-white p-6 shadow-[0_20px_50px_rgba(15,23,42,0.06)] sm:p-10">
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-emerald-500 animate-pulse" />
              <span className="font-semibold text-slate-900 text-sm">Pipeline: Autonomous Local Business Acquisition</span>
              <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-600">idempotent • version 2.4</span>
            </div>
            <span className="text-xs text-slate-500">Execution Engine: Celery + Redis Queue</span>
          </div>

          <div className="mt-8 grid gap-4 lg:grid-cols-5">
            {WORKFLOW_NODES.map((node, index) => {
              const Icon = node.icon;
              const isPast = index < activeStep;
              const isCurrent = index === activeStep;
              return (
                <div key={node.id} className="relative flex flex-col justify-between">
                  <div
                    className={`rounded-2xl border p-5 transition-all duration-300 h-full flex flex-col justify-between ${
                      isCurrent
                        ? "border-indigo-500 bg-indigo-50/40 shadow-lg ring-2 ring-indigo-500/20"
                        : isPast
                        ? "border-emerald-300 bg-emerald-50/20"
                        : "border-slate-200 bg-white hover:border-slate-300"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className={`grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br ${node.color} text-white shadow-sm`}>
                          <Icon className="h-5 w-5" />
                        </span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                            isCurrent
                              ? "bg-indigo-600 text-white"
                              : isPast
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {isCurrent ? "Active" : isPast ? "Complete" : node.type}
                        </span>
                      </div>

                      <h4 className="mt-4 font-bold text-slate-900 text-sm tracking-tight">{node.title}</h4>
                      <p className="mt-1 text-xs text-slate-500 leading-relaxed">{node.desc}</p>
                    </div>

                    <div className="mt-5 border-t border-slate-100 pt-3 flex items-center justify-between text-[11px]">
                      <span className="font-mono text-slate-400">{node.badge}</span>
                      {isPast ? (
                        <span className="flex items-center gap-1 font-semibold text-emerald-600">
                          <Check className="h-3.5 w-3.5" /> 200 OK
                        </span>
                      ) : isCurrent ? (
                        <span className="font-semibold text-indigo-600 animate-pulse">Processing...</span>
                      ) : (
                        <span className="text-slate-400">Standby</span>
                      )}
                    </div>
                  </div>

                  {/* Flow Arrow (Desktop) */}
                  {index < WORKFLOW_NODES.length - 1 && (
                    <div className="hidden lg:block absolute -right-3 top-1/2 -translate-y-1/2 z-10">
                      <div
                        className={`grid h-6 w-6 place-items-center rounded-full border bg-white shadow-sm ${
                          isPast ? "border-emerald-400 text-emerald-600" : "border-slate-200 text-slate-400"
                        }`}
                      >
                        <ChevronRight className="h-3.5 w-3.5" />
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Workflow execution metrics bar */}
          <div className="mt-8 grid grid-cols-2 gap-4 rounded-2xl border border-slate-100 bg-slate-50/60 p-4 sm:grid-cols-4 text-center">
            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Total Duration</p>
              <p className="mt-1 text-lg font-bold text-slate-900">3.8 Seconds</p>
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Outreach Lawful Basis</p>
              <p className="mt-1 text-lg font-bold text-emerald-600">100% Verified</p>
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">AI Token Cost</p>
              <p className="mt-1 text-lg font-bold text-slate-900">$0.00 (Ollama)</p>
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Audit Log Status</p>
              <p className="mt-1 text-lg font-bold text-indigo-600">Append-Only Immutable</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

