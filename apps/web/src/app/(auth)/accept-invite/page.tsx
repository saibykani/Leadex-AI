"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Users } from "lucide-react";
import { accounts, tokenFromUrl, type InvitePreview } from "@/lib/accounts";
import { api, ensureSession, session } from "@/lib/api";
import { AuthAlert, AuthButton, Field, PasswordField, Stagger, StaggerItem, StrengthMeter, SuccessBurst } from "@/components/auth/fields";

type Tokens = { access_token: string; refresh_token: string };

export default function AcceptInvitePage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [inv, setInv] = useState<InvitePreview | null>(null);
  const [me, setMe] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const t = tokenFromUrl(); setToken(t);
    if (!t) { setError("This invitation link is missing its token."); return; }
    accounts.previewInvite(t).then(setInv).catch((e) => setError((e as Error).message));
    void ensureSession().then((ok) => { if (ok) api<{ user: { email: string } }>("/auth/me").then((m) => setMe(m.user.email)).catch(() => {}); });
  }, []);

  async function accept(e: React.FormEvent) {
    e.preventDefault();
    if (!inv) return;
    setBusy(true); setError(null);
    try {
      if (inv.account_exists) await accounts.acceptInvite(token);
      else {
        await accounts.acceptInvite(token, name, pw);
        session.save(await api<Tokens>("/auth/login", { method: "POST", body: JSON.stringify({ email: inv.email, password: pw }) }));
      }
      setDone(true); setTimeout(() => router.push("/dashboard"), 1200);
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  const signedInAsInvitee = !!me && !!inv && me.toLowerCase() === inv.email.toLowerCase();
  return (
    <form onSubmit={accept} noValidate>
      <SuccessBurst show={done} label="Welcome aboard" />
      <Stagger className="space-y-5">
        <StaggerItem>
          <h1 className="bg-gradient-to-r from-[#0a84ff] via-[#5e5ce6] to-[#bf5af2] bg-clip-text text-[32px] font-semibold tracking-tight text-transparent">Join your team</h1>
          {inv && (
            <div className="mt-3 flex items-start gap-3 rounded-2xl bg-[#5e5ce6]/10 p-4 text-sm text-neutral-700">
              <Users className="mt-0.5 h-5 w-5 shrink-0 text-[#5e5ce6]" aria-hidden />
              <span>You&apos;ve been invited to <strong>{inv.organization_name}</strong> as <strong>{inv.role}</strong> ({inv.email}).</span>
            </div>
          )}
        </StaggerItem>
        <AuthAlert message={error} />
        {inv && !inv.account_exists && (
          <>
            <StaggerItem><Field id="name" label="Full name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} /></StaggerItem>
            <StaggerItem>
              <PasswordField id="password" label="Create a password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} />
              <div className="mt-2"><StrengthMeter value={pw} /></div>
            </StaggerItem>
            <StaggerItem><AuthButton type="submit" loading={busy} success={done} disabled={!name.trim() || pw.length < 10}>Create account &amp; join</AuthButton></StaggerItem>
          </>
        )}
        {inv && inv.account_exists && (signedInAsInvitee ? (
          <StaggerItem><AuthButton type="submit" loading={busy} success={done}>Accept invitation</AuthButton></StaggerItem>
        ) : (
          <StaggerItem>
            <p className="text-sm text-neutral-600">You already have a Leadex account. Sign in as <strong>{inv.email}</strong>, then open this link again.</p>
            <Link href="/login" className="mt-3 inline-flex h-11 items-center rounded-full bg-[#0a84ff] px-6 text-[15px] font-medium text-white">Sign in</Link>
          </StaggerItem>
        ))}
      </Stagger>
    </form>
  );
}
