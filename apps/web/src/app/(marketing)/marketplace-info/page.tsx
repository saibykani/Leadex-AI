import type { Metadata } from "next";
import { MarketplacePage } from "@/components/marketing/pages";

export const metadata: Metadata = { title: "Referral Marketplace | Leadex AI", description: "Match customer requirements with verified providers and track commissions." };

export default function Page() {
  return <MarketplacePage />;
}
