"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { accounts, tokenFromUrl } from "@/lib/accounts";
import { ensureSession } from "@/lib/api";

export default function VerifyEmailPage() {
  const [state, setState] = useState<"working" | "ok" | "error">("working");
  const [msg, setMsg] = useState("");
  const [next, setNext] = useState("/login");
  useEffect(() => {
    void ensureSession().then((ok) => setNext(ok ? "/dashboard" : "/login"));
    const t = tokenFromUrl();
    if (!t) { setState("error"); setMsg("This link is missing its token."); return; }
    accounts.verify(t).then(() => setState("ok")).catch((e) => { setState("error"); setMsg((e as Error).message); });
  }, []);
  return (
    <div className="space-y-5 text-center">
      <div className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-[#0a84ff]/10">
        {state === "working" ? <Loader2 className="h-7 w-7 animate-spin text-[#0a84ff]" />
          : state === "ok" ? <CheckCircle2 className="h-8 w-8 text-[#1a7f37]" /> : <XCircle className="h-8 w-8 text-[#ff375f]" />}
      </div>
      <h1 className="text-[28px] font-semibold tracking-tight">{state === "working" ? "Verifying…" : state === "ok" ? "Email verified" : "Verification failed"}</h1>
      <p className="text-[15px] text-neutral-600">{state === "ok" ? "Thanks, your email address is confirmed." : msg}</p>
      {state !== "working" && <Link href={next} className="inline-flex h-11 items-center rounded-full bg-[#0a84ff] px-6 text-[15px] font-medium text-white">Continue</Link>}
    </div>
  );
}
