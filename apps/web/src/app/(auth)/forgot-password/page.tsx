"use client";
import Link from "next/link";
import { useState } from "react";
import { MailCheck } from "lucide-react";
import { accounts } from "@/lib/accounts";
import { AuthAlert, AuthButton, Field, Stagger, StaggerItem } from "@/components/auth/fields";
import { DevLink } from "@/components/auth/DevLink";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [link, setLink] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try { const r = await accounts.forgot(email); setLink(r.dev_link); setSent(true); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  return (
    <form onSubmit={submit} noValidate>
      <Stagger className="space-y-5">
        <StaggerItem>
          <h1 className="bg-gradient-to-r from-[#0a84ff] via-[#5e5ce6] to-[#bf5af2] bg-clip-text text-[32px] font-semibold tracking-tight text-transparent">Reset password</h1>
          <p className="mt-2 text-[15px] text-neutral-600">Enter your account email and we&apos;ll send a reset link valid for 1 hour.</p>
        </StaggerItem>
        <AuthAlert message={error} />
        {sent ? (
          <StaggerItem>
            <div className="flex items-start gap-3 rounded-2xl bg-[#0a84ff]/10 p-4 text-sm text-neutral-700">
              <MailCheck className="mt-0.5 h-5 w-5 shrink-0 text-[#0a84ff]" aria-hidden />
              <span>If an account exists for <strong>{email}</strong>, a reset link is on its way.</span>
            </div>
            <div className="mt-3"><DevLink link={link} /></div>
          </StaggerItem>
        ) : (
          <>
            <StaggerItem><Field id="email" label="Email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></StaggerItem>
            <StaggerItem><AuthButton type="submit" loading={busy} disabled={!email.includes("@")}>Send reset link</AuthButton></StaggerItem>
          </>
        )}
        <StaggerItem><p className="text-center text-sm text-neutral-600"><Link href="/login" className="font-semibold text-[#0a6fd6] underline-offset-4 hover:underline">Back to sign in</Link></p></StaggerItem>
      </Stagger>
    </form>
  );
}
