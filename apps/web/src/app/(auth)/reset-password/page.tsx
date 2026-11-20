"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { accounts, tokenFromUrl } from "@/lib/accounts";
import { AuthAlert, AuthButton, PasswordField, Stagger, StaggerItem, StrengthMeter, SuccessBurst } from "@/components/auth/fields";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setToken(tokenFromUrl()), []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (pw !== pw2) { setError("Passwords do not match"); return; }
    setBusy(true); setError(null);
    try { await accounts.reset(token ?? "", pw); setDone(true); setTimeout(() => router.push("/login"), 1400); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  return (
    <form onSubmit={submit} noValidate>
      <SuccessBurst show={done} label="Password updated" />
      <Stagger className="space-y-5">
        <StaggerItem>
          <h1 className="bg-gradient-to-r from-[#0a84ff] via-[#5e5ce6] to-[#bf5af2] bg-clip-text text-[32px] font-semibold tracking-tight text-transparent">Choose a new password</h1>
          <p className="mt-2 text-[15px] text-neutral-600">At least 10 characters with letters and digits. You&apos;ll be signed out of all devices.</p>
        </StaggerItem>
        <AuthAlert message={token === "" ? "This reset link is missing its token. Request a new one." : error} />
        <StaggerItem>
          <PasswordField id="password" label="New password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />
          <div className="mt-2"><StrengthMeter value={pw} /></div>
        </StaggerItem>
        <StaggerItem><PasswordField id="password2" label="Confirm password" autoComplete="new-password" value={pw2} onChange={(e) => setPw2(e.target.value)} /></StaggerItem>
        <StaggerItem><AuthButton type="submit" loading={busy} success={done} disabled={!token || pw.length < 10}>Update password</AuthButton></StaggerItem>
        <StaggerItem><p className="text-center text-sm text-neutral-600"><Link href="/forgot-password" className="font-semibold text-[#0a6fd6] underline-offset-4 hover:underline">Request a new link</Link></p></StaggerItem>
      </Stagger>
    </form>
  );
}
