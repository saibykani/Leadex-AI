import type { Metadata } from "next";
import { LeadGenPage } from "@/components/marketing/pages";

export const metadata: Metadata = { title: "Lead Generation | Leadex AI", description: "Discover businesses by region and industry with source tracking and compliance." };

export default function Page() {
  return <LeadGenPage />;
}
