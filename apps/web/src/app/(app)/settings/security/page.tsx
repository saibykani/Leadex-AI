"use client";
import { useEffect, useState } from "react";
import { KeyRound, Mail, MonitorSmartphone, ShieldCheck } from "lucide-react";
import { accounts, deviceLabel, type DeviceSession } from "@/lib/accounts";
import { DevLink } from "@/components/auth/DevLink";
import { mfaApi } from "@/lib/compliance";
import { useSession } from "@/lib/session-context";
import { Alert, Badge, Button, Input, PageHeader, Skeleton, useToast } from "@/components/ui";

export default function SecurityPage() {
  const { reload } = useSession();
  const toast = useToast();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { mfaApi.status().then((s) => setEnabled(s.mfa_enabled)).catch((e) => setError((e as Error).message)); }, []);

  async function act(fn: () => Promise<void>) {
    setBusy(true); setError(null);
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  const start = () => act(async () => { setSetup(await mfaApi.setup()); setCode(""); });
  const verify = (e: React.FormEvent) => { e.preventDefault(); void act(async () => {
    await mfaApi.verify(code); setEnabled(true); setSetup(null); setCode(""); toast("Two-factor authentication enabled", "success"); await reload();
  }); };
  const disable = (e: React.FormEvent) => { e.preventDefault(); void act(async () => {
    await mfaApi.disable(code, password); setEnabled(false); setCode(""); setPassword(""); toast("Two-factor authentication disabled", "success"); await reload();
  }); };

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Security" description="Protect your account with an authenticator app (TOTP)." />
      {error && <Alert>{error}</Alert>}
      <section className="card space-y-5 p-6">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-[15px] font-semibold"><ShieldCheck className="h-4 w-4 text-accent" />Two-factor authentication</h2>
          {enabled === null ? <Skeleton className="h-6 w-20" /> : enabled ? <Badge tone="success">Enabled</Badge> : <Badge>Off</Badge>}
        </div>

        {enabled === false && !setup && (
          <div className="space-y-3">
            <p className="text-sm text-muted">After enabling, you will need a 6-digit code from your authenticator app each time you sign in.</p>
            <Button onClick={start} loading={busy}><KeyRound className="h-4 w-4" />Set up authenticator</Button>
          </div>
        )}

        {enabled === false && setup && (
          <form onSubmit={verify} className="space-y-4">
            <ol className="list-decimal space-y-2 pl-5 text-sm text-neutral-700">
              <li>In your authenticator app, add an account using the setup key below (or paste the otpauth link into an app that accepts it).</li>
              <li>Enter the 6-digit code the app shows.</li>
            </ol>
            <div>
              <div className="label">Setup key</div>
              <code className="block select-all break-all rounded-xl bg-raised px-4 py-3 font-mono text-sm tracking-wider">{setup.secret}</code>
            </div>
            <div>
              <div className="label">otpauth link</div>
              <code className="block select-all break-all rounded-xl bg-raised px-4 py-3 font-mono text-xs text-muted">{setup.otpauth_uri}</code>
            </div>
            <div><label className="label" htmlFor="code">Verification code</label>
              <Input id="code" inputMode="numeric" autoComplete="one-time-code" maxLength={8} value={code} onChange={(e) => setCode(e.target.value.trim())} /></div>
            <div className="flex gap-2">
              <Button type="submit" loading={busy} disabled={code.length < 6}>Verify and enable</Button>
              <Button type="button" variant="ghost" onClick={() => setSetup(null)}>Cancel</Button>
            </div>
          </form>
        )}

        {enabled && (
          <form onSubmit={disable} className="space-y-4">
            <p className="text-sm text-muted">To turn off two-factor authentication, confirm your password and a current code.</p>
            <div><label className="label" htmlFor="pw">Password</label>
              <Input id="pw" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
            <div><label className="label" htmlFor="dcode">Authenticator code</label>
              <Input id="dcode" inputMode="numeric" autoComplete="one-time-code" maxLength={8} value={code} onChange={(e) => setCode(e.target.value.trim())} /></div>
            <Button type="submit" variant="outline" loading={busy} disabled={!password || code.length < 6}>Disable two-factor</Button>
          </form>
        )}
      </section>
      <EmailVerification />
      <Sessions />
    </div>
  );
}

function EmailVerification() {
  const { me, reload } = useSession();
  const [link, setLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const verified = !!me.user.email_verified_at;
  async function send() {
    setBusy(true); setMsg(null);
    try { const r = await accounts.requestVerify(); setLink(r.dev_link); setMsg(r.simulated ? "Verification email simulated (development)." : "Verification email sent."); await reload(); }
    catch (e) { setMsg((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <section className="card space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold"><Mail className="h-4 w-4 text-accent" />Email address</h2>
        {verified ? <Badge tone="success">Verified</Badge> : <Badge tone="warning">Not verified</Badge>}
      </div>
      <p className="text-sm text-muted">{me.user.email}</p>
      {!verified && <Button variant="outline" loading={busy} onClick={send}>Send verification link</Button>}
      {msg && <p className="text-sm text-muted">{msg}</p>}
      <DevLink link={link} />
    </section>
  );
}

function Sessions() {
  const toast = useToast();
  const [rows, setRows] = useState<DeviceSession[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => accounts.sessions().then(setRows).catch((e) => setError((e as Error).message));
  useEffect(() => { void load(); }, []);
  async function others() {
    try { const r = await accounts.revokeOthers(); toast(`Signed out ${r.revoked} other session${r.revoked === 1 ? "" : "s"}`, "success"); await load(); }
    catch (e) { setError((e as Error).message); }
  }
  async function revoke(id: string) {
    try { await accounts.revokeSession(id); await load(); } catch (e) { setError((e as Error).message); }
  }
  return (
    <section className="card space-y-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold"><MonitorSmartphone className="h-4 w-4 text-accent" />Signed-in devices</h2>
        {rows && rows.length > 1 && <Button variant="outline" size="sm" onClick={others}>Sign out all other devices</Button>}
      </div>
      {error && <Alert>{error}</Alert>}
      {!rows ? <Skeleton className="h-24 w-full" /> : (
        <ul className="divide-y divide-line">
          {rows.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
              <span className="font-medium">{deviceLabel(s.user_agent)}</span>
              <span className="text-xs text-muted">{s.ip_address ?? "unknown IP"} · signed in {new Date(s.created_at).toLocaleString()}</span>
              <button type="button" className="ml-auto text-xs font-medium text-red-600 hover:underline" onClick={() => revoke(s.id)}>Sign out</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
