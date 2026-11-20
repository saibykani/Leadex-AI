"use client";
import { useState, type FormEvent } from "react";
import { MailCheck } from "lucide-react";
import { Alert, Button, Input } from "@/components/ui";
import { DevLink } from "@/components/auth/DevLink";
import { portal, type Delivery } from "@/lib/portal";

export default function PortalLogin() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<Delivery | null>(null);
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError(null);
    try { setSent(await portal.login(email)); } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  };
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f6f5ff] px-4">
      <div className="w-full max-w-md space-y-5 rounded-3xl bg-white p-8 shadow-sm ring-1 ring-black/5">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Partner &amp; customer portal</h1>
          <p className="mt-2 text-sm text-neutral-600">Enter the email address you were invited with. We will send a single-use sign-in link, valid for 30 minutes.</p>
        </div>
        {error && <Alert>{error}</Alert>}
        {sent ? (
          <div className="space-y-3">
            <div className="flex items-start gap-3 rounded-2xl bg-[#0a84ff]/10 p-4 text-sm text-neutral-700">
              <MailCheck className="mt-0.5 h-5 w-5 shrink-0 text-[#0a84ff]" aria-hidden />
              <span>If portal access exists for <strong>{email}</strong>, a sign-in link is on its way.</span>
            </div>
            {sent.dev_links.length > 1 ? sent.dev_links.map((l) => <DevLink key={l} link={l} />) : <DevLink link={sent.dev_link} />}
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4" noValidate>
            <Input type="email" autoComplete="email" placeholder="you@company.com" value={email} onChange={(e) => setEmail(e.target.value)} aria-label="Email" />
            <Button type="submit" loading={busy} disabled={!email.includes("@")} className="w-full">Email me a sign-in link</Button>
          </form>
        )}
      </div>
    </main>
  );
}
