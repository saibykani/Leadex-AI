"use client";
import clsx from "clsx";
import type { ReactNode } from "react";
import { label, type Match } from "@/lib/marketplace";

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "good" | "warn" | "bad"; children: ReactNode }) {
  return (
    <span className={clsx("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
      tone === "good" && "bg-emerald-50 text-emerald-700", tone === "warn" && "bg-amber-50 text-amber-700",
      tone === "bad" && "bg-red-50 text-red-700", tone === "neutral" && "bg-raised text-neutral-700")}>
      {children}
    </span>
  );
}

export function VerificationBadge({ status }: { status: string }) {
  const tone = status === "verified" ? "good" : status === "rejected" ? "bad" : "warn";
  return <Badge tone={tone}>{label(status)}</Badge>;
}

export function Field({ label: l, children }: { label: string; children: ReactNode }) {
  return <label className="block text-sm"><span className="mb-1 block text-xs text-muted">{l}</span>{children}</label>;
}

export const selectCls = "h-12 w-full rounded-xl border border-line bg-white px-3 text-[15px] outline-none focus:border-accent";
export const areaCls = "w-full rounded-xl border border-line bg-white px-4 py-3 text-[15px] outline-none focus:border-accent";

export function Tabs<T extends string>({ value, options, onChange }: { value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex rounded-full bg-raised p-1">
      {options.map(([v, l]) => (
        <button key={v} onClick={() => onChange(v)}
          className={clsx("rounded-full px-4 py-1.5 text-sm transition", value === v ? "bg-white shadow-sm font-medium" : "text-muted")}>
          {l}
        </button>
      ))}
    </div>
  );
}

export function MatchCard({ m, action }: { m: Match; action?: ReactNode }) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="font-medium">{m.provider_name ?? m.provider_id}</div>
          {m.explanation.unverified_flag && (
            <div className="mt-0.5 text-xs text-amber-700">Not verified — ranked lower (score × {m.explanation.penalty})</div>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-2xl font-semibold tabular-nums">{m.score}</span>
          {action}
        </div>
      </div>
      <ul className="mt-3 space-y-2">
        {Object.entries(m.explanation.factors).map(([k, f]) => (
          <li key={k} className="text-xs">
            <div className="flex justify-between"><span className="font-medium">{label(k)} <span className="text-muted">(weight {f.weight})</span></span><span className="tabular-nums">{Math.round(f.score * 100)}%</span></div>
            <div className="mt-1 h-1.5 rounded-full bg-raised"><div className="h-1.5 rounded-full bg-accent" style={{ width: `${f.score * 100}%` }} /></div>
            <div className="mt-0.5 text-muted">{f.reason}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}
