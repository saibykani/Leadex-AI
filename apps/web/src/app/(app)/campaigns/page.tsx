"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Megaphone, Plus } from "lucide-react";
import { useSession } from "@/lib/session-context";
import { Alert, EmptyState } from "@/components/ui";
import { campaigns, type Campaign } from "@/lib/communication";
import type { Page } from "@/lib/api";
import { Badge } from "./_ui/badge";

export default function CampaignsPage() {
  const { can } = useSession();
  const [data, setData] = useState<Page<Campaign> | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { campaigns.list().then(setData).catch((e) => setError(e.message)); }, []);
  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Campaigns</h1>
          <p className="mt-1 text-sm text-muted">Every campaign needs approval, and every recipient is checked by the compliance gate before any send.</p>
        </div>
        {can("campaigns:write") && (
          <Link href="/campaigns/new" className="inline-flex h-10 items-center gap-2 rounded-full bg-accent px-5 text-sm font-medium text-white hover:bg-accent-strong"><Plus className="h-4 w-4" />New campaign</Link>
        )}
      </div>
      {error && <Alert>{error}</Alert>}
      {data?.items.length === 0 && <EmptyState icon={<Megaphone className="h-5 w-5" />} title="No campaigns yet" body="Create an email or WhatsApp campaign, add approved leads, and submit it for approval." />}
      {!!data?.items.length && (
        <ul className="card divide-y divide-line">
          {data.items.map((c) => (
            <li key={c.id}>
              <Link href={`/campaigns/${c.id}`} className="flex items-center justify-between px-5 py-3.5 hover:bg-raised">
                <div>
                  <div className="text-sm font-medium">{c.name}</div>
                  <div className="text-xs text-muted capitalize">{c.channel} · created {new Date(c.created_at).toLocaleDateString()}</div>
                </div>
                <Badge value={c.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
