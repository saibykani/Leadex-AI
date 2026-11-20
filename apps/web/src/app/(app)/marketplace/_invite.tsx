"use client";
import { useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui";
import { DevLink } from "@/components/auth/DevLink";
import { portalInvite, type Invite } from "@/lib/portal";

/** Staff action: email a single-use portal sign-in link to a provider or a requirement's customer. */
export function InviteToPortal({ kind, id }: { kind: "provider" | "requirement"; id: string }) {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<Invite | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const send = async () => {
    setBusy(true); setErr(null);
    try { setRes(await portalInvite[kind](id)); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-2">
      <Button variant="outline" className="h-9 px-4 text-sm" loading={busy} onClick={send}><Send className="mr-1.5 h-3.5 w-3.5" />Invite to portal</Button>
      {err && <p className="text-xs text-danger">{err}</p>}
      {res && <p className="text-xs text-muted">{res.simulated ? "Simulated invite for" : "Invite sent to"} {res.email}.</p>}
      {res && <DevLink link={res.dev_link} />}
    </div>
  );
}
