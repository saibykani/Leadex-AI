"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CreditCard, X } from "lucide-react";
import { BILLING_EVENT, type ApiError } from "@/lib/api";

/** Listens for any 402 from the API (plan limit, inactive subscription, budget hard stop) and links to /billing. */
export function BillingNotice() {
  const [err, setErr] = useState<ApiError | null>(null);
  useEffect(() => {
    const h = (e: Event) => setErr((e as CustomEvent<ApiError>).detail);
    window.addEventListener(BILLING_EVENT, h);
    return () => window.removeEventListener(BILLING_EVENT, h);
  }, []);
  useEffect(() => {
    if (!err) return;
    const t = setTimeout(() => setErr(null), 10000);
    return () => clearTimeout(t);
  }, [err]);
  if (!err) return null;
  return (
    <div role="alert" className="fixed bottom-4 left-1/2 z-[70] flex w-[min(92vw,32rem)] -translate-x-1/2 items-start gap-3 rounded-2xl bg-white px-4 py-3 text-sm shadow-lift ring-1 ring-danger/30">
      <CreditCard className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
      <div className="min-w-0 flex-1">
        <div className="font-medium text-neutral-900">{err.message}</div>
        <Link href="/billing" onClick={() => setErr(null)} className="mt-1 inline-block text-accent hover:underline">Review plan &amp; billing</Link>
      </div>
      <button onClick={() => setErr(null)} aria-label="Dismiss" className="rounded-full p-1 text-muted hover:bg-raised"><X className="h-4 w-4" /></button>
    </div>
  );
}
