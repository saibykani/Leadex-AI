"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Alert } from "@/components/ui";
import { portal, portalToken } from "@/lib/portal";

export default function PortalAuth() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false); // links are single-use: exchange exactly once (React strict mode runs effects twice)
  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) { setError("This sign-in link is incomplete."); return; }
    window.history.replaceState(null, "", "/portal/auth"); // keep the token out of history and referrers
    portal.exchange(token)
      .then((s) => { portalToken.set(s.portal_token); router.replace("/portal"); })
      .catch((e: Error) => setError(e.message));
  }, [router]);
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f6f5ff] px-4">
      <div className="w-full max-w-md space-y-4 rounded-3xl bg-white p-8 text-center shadow-sm ring-1 ring-black/5">
        {error ? (<>
          <Alert>{error}</Alert>
          <Link href="/portal/login" className="text-sm font-semibold text-[#0a6fd6] hover:underline">Request a new link</Link>
        </>) : <p className="text-sm text-neutral-600">Signing you in…</p>}
      </div>
    </main>
  );
}
