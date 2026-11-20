"use client";
import { useEffect, useState } from "react";
import { Phone } from "lucide-react";
import { Badge, type Tone } from "@/components/ui";
import { telephonyApi, type TelephonyStatus } from "./_lib/telephony";

const MODE: Record<TelephonyStatus["mode"], { label: string; tone: Tone; text: string }> = {
  not_configured: { label: "Not configured", tone: "neutral", text: "No Twilio credentials found. Calls are simulated (nobody is contacted)." },
  needs_public_url: { label: "Needs public URL", tone: "warning", text: "Twilio credentials found, but Twilio cannot reach the webhooks. Set an https PUBLIC_WEBHOOK_BASE_URL." },
  simulated: { label: "Simulated", tone: "neutral", text: "Twilio is ready, but this is not production and test calls are off. Allowed calls are simulated." },
  test_allowlist: { label: "Test mode (allowlist)", tone: "accent", text: "Real calls are placed ONLY to numbers on TEST_CALL_ALLOWLIST. Everything else is simulated." },
  live: { label: "Live", tone: "success", text: "Production: calls that pass every compliance check are really dialled." },
};

export function TelephonyCard() {
  const [st, setSt] = useState<TelephonyStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => { telephonyApi.status().then((s) => { setSt(s); setOpen(s.mode !== "live" && s.mode !== "test_allowlist"); }).catch((e) => setErr(e.message)); }, []);
  if (err) return <div className="card p-5 text-sm text-muted">Telephony status unavailable: {err}</div>;
  if (!st) return <div className="card p-5 text-sm text-muted">Loading telephony status…</div>;
  const m = MODE[st.mode];
  return (
    <div className="card space-y-3 p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-medium"><Phone className="h-4 w-4" /> Telephony · Twilio <Badge tone={m.tone} dot>{m.label}</Badge></h2>
        <button type="button" className="text-sm text-accent" onClick={() => setOpen((o) => !o)}>{open ? "Hide setup steps" : "Setup steps"}</button>
      </div>
      <p className="text-sm text-muted">{m.text}</p>
      <dl className="grid grid-cols-1 gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
        <div><dt className="inline text-muted">Environment: </dt><dd className="inline font-mono">{st.app_env}</dd></div>
        <div><dt className="inline text-muted">Credentials: </dt><dd className="inline">{st.credential_source === "org" ? "organization integration" : st.credential_source === "env" ? "server env (TWILIO_*)" : "none"}</dd></div>
        <div><dt className="inline text-muted">From number: </dt><dd className="inline font-mono">{st.from_number ?? "—"}</dd></div>
        <div><dt className="inline text-muted">Public webhook base: </dt><dd className="inline break-all font-mono">{st.public_base_url ?? "—"}</dd></div>
        <div><dt className="inline text-muted">Test calls: </dt><dd className="inline">{st.allow_test_calls ? "allowed" : "off"}</dd></div>
        <div><dt className="inline text-muted">Allowlist: </dt><dd className="inline font-mono">{st.test_allowlist.length ? st.test_allowlist.join(", ") : "—"}</dd></div>
      </dl>
      {st.status !== "configured" && <p className="text-xs text-warning">{st.detail}</p>}
      {open && (
        <ol className="list-decimal space-y-1.5 pl-5 text-sm">
          <li>Create a Twilio account (a free trial works) at <span className="font-mono">twilio.com/try-twilio</span>.</li>
          <li>In the Twilio console, verify your own phone under <b>Phone Numbers → Verified Caller IDs</b>. Trial accounts can ONLY call verified numbers.</li>
          <li>Get a Twilio phone number (the trial gives one free number). This is <span className="font-mono">TWILIO_FROM_NUMBER</span>.</li>
          <li>Start a public https tunnel to the API: <span className="font-mono">cloudflared tunnel --url http://localhost:8010</span> (or <span className="font-mono">ngrok http 8010</span>).</li>
          <li>Set <span className="font-mono">PUBLIC_WEBHOOK_BASE_URL=https://&lt;your-tunnel-host&gt;</span> in <span className="font-mono">.env</span> (no trailing path).</li>
          <li>Set <span className="font-mono">TWILIO_ACCOUNT_SID</span>, <span className="font-mono">TWILIO_AUTH_TOKEN</span>, <span className="font-mono">TWILIO_FROM_NUMBER</span> in <span className="font-mono">.env</span> — or save them per organization under Integrations → Twilio (credentials <span className="font-mono">account_sid</span>, <span className="font-mono">auth_token</span>, <span className="font-mono">from_number</span>).</li>
          <li>For local testing on your own phone: <span className="font-mono">ALLOW_TEST_CALLS=true</span> and <span className="font-mono">TEST_CALL_ALLOWLIST=+91XXXXXXXXXX</span> (E.164, comma-separated). Restart the API.</li>
          <li>Make sure the lead has that phone number and country, voice consent, and is approved for outreach; publish the agent; then start the call.</li>
        </ol>
      )}
      <p className="text-xs text-muted">Calling Indian numbers commercially needs TRAI DLT / telemarketer registration and the person&apos;s consent. See docs/TELEPHONY_SETUP.md.</p>
    </div>
  );
}
