"use client";
import Link from "next/link";
import { useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight, Calculator, CheckCircle2, DollarSign, HelpCircle,
  Percent, Sparkles, TrendingUp, Users, Zap
} from "lucide-react";
import { serif } from "./fonts";

export function InteractiveRoiCalculator() {
  const [prospects, setProspects] = useState(1500);
  const [teamSize, setTeamSize] = useState(3);

  // Calculations based on docs/COST_ESTIMATION.md
  // Traditional stack: Discovery ($450) + AI Dialers ($800) + Website Tools ($250) + Automation ($200) + Rep Seats ($150 * reps)
  const traditionalCost = Math.round(450 + 250 + 200 + prospects * 0.45 + teamSize * 150);

  // Leadex AI: Core platform + self-hosted Ollama ($0 token cost) + raw telephony ($0.015/min)
  const leadexCost = Math.round(99 + prospects * 0.05 + teamSize * 25);
  const monthlySavings = traditionalCost - leadexCost;
  const hoursSaved = Math.round(teamSize * 36 + prospects * 0.04);
  const estimatedDeals = Math.round((prospects * 0.032));

  return (
    <section className="relative overflow-hidden bg-white py-24 sm:py-32">
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6">
        <div className="mx-auto max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50/70 px-4 py-1 text-xs font-semibold text-emerald-800">
            <Calculator className="h-3.5 w-3.5 text-emerald-600" /> Transparent Unit Economics
          </div>
          <h2 className={`${serif.className} mt-4 text-[38px] leading-[1.08] tracking-tight text-slate-900 sm:text-[56px]`}>
            Calculate your monthly savings. <br className="hidden sm:inline" />
            <span className="italic text-emerald-600">Zero token tax. Zero markup.</span>
          </h2>
          <p className="mt-4 text-base leading-relaxed text-slate-600 sm:text-lg">
            See the exact cost differential between a fragmented 5-tool enterprise stack and Leadex AI&apos;s open-source architecture with self-hosted Ollama.
          </p>
        </div>

        {/* Calculator Widget */}
        <div className="mt-14 mx-auto max-w-5xl rounded-3xl border border-slate-200/90 bg-slate-50/50 p-6 shadow-[0_20px_50px_rgba(15,23,42,0.06)] sm:p-10">
          <div className="grid gap-10 lg:grid-cols-12 items-center">
            {/* Left 6 cols: Sliders */}
            <div className="lg:col-span-6 space-y-8">
              {/* Slider 1: Prospects */}
              <div>
                <div className="flex items-center justify-between">
                  <label className="text-sm font-bold text-slate-900">
                    Monthly Target Prospects
                  </label>
                  <span className="rounded-lg bg-blue-50 px-3 py-1 font-mono text-sm font-bold text-blue-700">
                    {prospects.toLocaleString()} Leads
                  </span>
                </div>
                <input
                  type="range"
                  min="200"
                  max="10000"
                  step="100"
                  value={prospects}
                  onChange={(e) => setProspects(Number(e.target.value))}
                  className="mt-3 h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-blue-600"
                />
                <div className="mt-1.5 flex justify-between text-[11px] text-slate-400">
                  <span>200 leads</span>
                  <span>5,000 leads</span>
                  <span>10,000 leads</span>
                </div>
              </div>

              {/* Slider 2: Team Size */}
              <div>
                <div className="flex items-center justify-between">
                  <label className="text-sm font-bold text-slate-900">
                    Sales Team / Workspace Reps
                  </label>
                  <span className="rounded-lg bg-indigo-50 px-3 py-1 font-mono text-sm font-bold text-indigo-700">
                    {teamSize} {teamSize === 1 ? "Member" : "Members"}
                  </span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="20"
                  step="1"
                  value={teamSize}
                  onChange={(e) => setTeamSize(Number(e.target.value))}
                  className="mt-3 h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-indigo-600"
                />
                <div className="mt-1.5 flex justify-between text-[11px] text-slate-400">
                  <span>1 person</span>
                  <span>10 people</span>
                  <span>20 people</span>
                </div>
              </div>

              {/* Key Assumptions */}
              <div className="space-y-2 rounded-2xl border border-slate-200/80 bg-white p-4 text-xs text-slate-600">
                <span className="font-bold text-slate-900 uppercase text-[11px] tracking-wider block">Documentation Principles:</span>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                  <span>Open-source AI by default: Ollama LLMs run with $0 token billing.</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                  <span>Raw carrier telephony rates with zero platform margin.</span>
                </div>
              </div>
            </div>

            {/* Right 6 cols: Live Comparison Card */}
            <div className="lg:col-span-6 rounded-2xl border border-emerald-200 bg-white p-6 shadow-md">
              <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Monthly Projected Impact</span>
                <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-bold text-emerald-800">
                  ~85% Cost Reduction
                </span>
              </div>

              <div className="mt-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-slate-500">Fragmented 5-Tool Stack</p>
                    <p className="text-xs text-slate-400">(Apollo + Vapi + Webflow + Zapier + CRM)</p>
                  </div>
                  <span className="font-mono text-lg font-semibold text-rose-600 line-through">
                    ${traditionalCost.toLocaleString()} /mo
                  </span>
                </div>

                <div className="flex items-center justify-between rounded-xl bg-emerald-50/70 p-3.5 border border-emerald-200">
                  <div>
                    <p className="font-bold text-slate-900 text-sm">Leadex AI Unified Monorepo</p>
                    <p className="text-xs text-emerald-700">Self-hosted AI + RLS multi-tenant</p>
                  </div>
                  <span className="font-mono text-2xl font-bold text-emerald-700">
                    ${leadexCost.toLocaleString()} <span className="text-xs font-normal text-slate-500">/mo</span>
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 pt-2">
                  <div className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-center">
                    <p className="text-[11px] font-semibold text-slate-500 uppercase">Monthly Net Savings</p>
                    <p className="mt-1 font-mono text-xl font-bold text-emerald-600">
                      +${monthlySavings.toLocaleString()}
                    </p>
                  </div>

                  <div className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-center">
                    <p className="text-[11px] font-semibold text-slate-500 uppercase">Rep Hours Saved</p>
                    <p className="mt-1 font-mono text-xl font-bold text-indigo-600">
                      ~{hoursSaved} hrs/mo
                    </p>
                  </div>
                </div>

                <div className="pt-2">
                  <Link
                    href="/register"
                    className="block w-full text-center rounded-full bg-slate-900 py-3 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 transition-all"
                  >
                    Start Saving with Leadex AI Today →
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}