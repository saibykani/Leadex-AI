"use client";
import clsx from "clsx";
import { STATUS_STYLES } from "@/lib/agents";

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={clsx("inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium", STATUS_STYLES[status] ?? "bg-neutral-100 text-neutral-700")}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function SimulatedBadge({ on = true }: { on?: boolean }) {
  if (!on) return null;
  return <span className="inline-flex rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800" title="Not produced by a real AI model or telephony provider">simulated</span>;
}

export function Textarea(p: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...p} className={clsx("w-full rounded-xl border border-line bg-white px-4 py-3 text-[15px] outline-none focus:border-accent focus:ring-4 focus:ring-accent/15", p.className)} />;
}
