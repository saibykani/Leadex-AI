"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { GitBranch } from "lucide-react";
import { useSession } from "@/lib/session-context";
import { Alert, EmptyState } from "@/components/ui";
import { REFERRAL_STATUSES, label, mkt, type Referral } from "@/lib/marketplace";

export default function ReferralsBoard() {
  const { can } = useSession();
  const [items, setItems] = useState<Referral[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (can("marketplace:write")) mkt.referrals().then((p) => setItems(p.items)).catch((e) => setError(e.message));
  }, [can]);

  if (!can("marketplace:write")) return <EmptyState icon={<GitBranch className="h-5 w-5" />} title="No access" body="You need the marketplace:write permission." />;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Referrals</h1>
        <p className="mt-1 text-sm text-muted">Pipeline by status. Create referrals from matches on the Marketplace page.</p>
      </div>
      {error && <Alert>{error}</Alert>}
      {items && items.length === 0 && <EmptyState icon={<GitBranch className="h-5 w-5" />} title="No referrals yet" body="Run matching on a requirement and refer a provider." />}
      {items && items.length > 0 && (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {REFERRAL_STATUSES.map((s) => {
            const col = items.filter((r) => r.status === s);
            return (
              <div key={s} className="w-56 shrink-0 rounded-2xl bg-raised p-2">
                <div className="flex justify-between px-2 py-1 text-xs font-medium text-muted"><span>{label(s)}</span><span>{col.length}</span></div>
                <div className="space-y-2">
                  {col.map((r) => (
                    <Link key={r.id} href={`/referrals/${r.id}`} className="block rounded-xl bg-white p-3 text-sm shadow-sm hover:shadow">
                      <div className="font-medium">{r.requirement_title}</div>
                      <div className="text-xs text-muted">{r.provider_name}</div>
                    </Link>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
