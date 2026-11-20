"use client";
import { useCallback, useEffect, useState } from "react";
import { Building2, Globe, Hash, UserPlus } from "lucide-react";
import { api, type Member } from "@/lib/api";
import { accounts, type Invite } from "@/lib/accounts";
import { DevLink } from "@/components/auth/DevLink";
import { useSession } from "@/lib/session-context";
import { Alert, Badge, Button, Input, PageHeader, Select, Skeleton, Table, useToast } from "@/components/ui";

const ROLES = ["Viewer", "Sales Rep", "Manager", "Admin", "Owner"];

export default function SettingsPage() {
  const { current, can } = useSession();
  const toast = useToast();
  const org = current.organization;
  const [members, setMembers] = useState<Member[] | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("Viewer");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => api<Member[]>(`/organizations/${org.id}/members`).then(setMembers).catch((e) => setError(e.message)), [org.id]);
  useEffect(() => { void load(); }, [load]);

  const [invites, setInvites] = useState<Invite[] | null>(null);
  const [devLink, setDevLink] = useState<string | null>(null);
  const loadInvites = useCallback(() => accounts.invites(org.id).then(setInvites).catch(() => setInvites([])), [org.id]);
  useEffect(() => { void loadInvites(); }, [loadInvites]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null); setDevLink(null);
    try {
      const r = await accounts.invite(org.id, email, role);
      setDevLink(r.dev_link);
      setEmail(""); toast(r.simulated ? "Invitation created (email simulated)" : "Invitation sent", "success"); await loadInvites();
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }
  async function revoke(id: string) {
    try { await accounts.revokeInvite(org.id, id); toast("Invitation revoked", "success"); await loadInvites(); }
    catch (err) { setError((err as Error).message); }
  }

  return (
    <div className="max-w-4xl space-y-8">
      <PageHeader title="Organization" description="Workspace profile and team access." />
      {error && <Alert>{error}</Alert>}

      <section className="card grid gap-6 p-6 sm:grid-cols-3">
        <Info icon={<Building2 className="h-4 w-4" />} label="Name" value={org.name} />
        <Info icon={<Hash className="h-4 w-4" />} label="Slug" value={<span className="font-mono">{org.slug}</span>} />
        <Info icon={<Globe className="h-4 w-4" />} label="Country" value={org.country_code ?? "Not set"} />
        <div className="flex items-center gap-2 text-sm text-muted sm:col-span-3">
          <Badge tone={org.status === "active" ? "success" : "warning"}>{org.status}</Badge>
          {org.is_platform_owner && <Badge tone="violet">Platform owner</Badge>}
          <span>Created {new Date(org.created_at).toLocaleDateString()}</span>
          <span className="ml-auto">Your role: <strong className="text-neutral-900">{current.role}</strong></span>
        </div>
      </section>

      {can("members:write") && (
        <form onSubmit={invite} className="card space-y-4 p-6">
          <div>
            <h2 className="flex items-center gap-2 text-[15px] font-semibold"><UserPlus className="h-4 w-4 text-accent" />Invite a teammate</h2>
            <p className="text-sm text-muted">They get an email link (valid 7 days) to join. New people create their account from the link.</p>
          </div>
          <DevLink link={devLink} />
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-56 flex-1"><label className="label" htmlFor="m-email">Email</label>
              <Input id="m-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="h-11" /></div>
            <div><label className="label" htmlFor="m-role">Role</label>
              <Select id="m-role" value={role} onChange={(e) => setRole(e.target.value)} className="h-11">{ROLES.map((r) => <option key={r}>{r}</option>)}</Select></div>
            <Button type="submit" loading={busy}>Send invite</Button>
          </div>
          {!!invites?.length && (
            <div className="space-y-2 border-t border-line pt-4">
              <div className="text-xs font-medium text-muted">Pending invitations</div>
              {invites.map((i) => (
                <div key={i.id} className="flex flex-wrap items-center gap-3 text-sm">
                  <span className="font-medium">{i.email}</span><Badge>{i.role}</Badge>
                  <span className="text-xs text-muted">expires {new Date(i.expires_at).toLocaleDateString()}</span>
                  <button type="button" className="ml-auto text-xs font-medium text-red-600 hover:underline" onClick={() => revoke(i.id)}>Revoke</button>
                </div>
              ))}
            </div>
          )}
        </form>
      )}

      <section className="space-y-3">
        <h2 className="text-[15px] font-semibold">Members {members && <span className="font-normal text-muted">· {members.length}</span>}</h2>
        {!members ? <Skeleton className="h-40 w-full" /> : (
          <Table head={["Name", "Email", "Role", "Status"]}>
            {members.map((m) => (
              <tr key={m.id}>
                <td className="px-5 py-3.5">
                  <div className="flex items-center gap-3">
                    <span className="grid h-8 w-8 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent">{m.full_name.slice(0, 1).toUpperCase()}</span>
                    <span className="font-medium">{m.full_name}</span>
                  </div>
                </td>
                <td className="px-5 py-3.5 text-muted">{m.email}</td>
                <td className="px-5 py-3.5"><Badge tone={m.role === "Owner" ? "violet" : m.role === "Admin" ? "accent" : "neutral"}>{m.role}</Badge></td>
                <td className="px-5 py-3.5"><Badge tone={m.status === "active" ? "success" : "warning"}>{m.status}</Badge></td>
              </tr>
            ))}
          </Table>
        )}
      </section>
    </div>
  );
}

function Info({ icon, label, value }: { icon: React.ReactNode; label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs text-muted">{icon}{label}</div>
      <div className="mt-1 text-[15px] font-medium">{value}</div>
    </div>
  );
}
