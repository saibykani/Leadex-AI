import type { Metadata } from "next";
import { ProductPage } from "@/components/marketing/pages";

export const metadata: Metadata = { title: "Product | Leadex AI", description: "Discovery, CRM, AI voice agents, outreach, website studio, marketplace and analytics in one platform." };

export default function Page() {
  return <ProductPage />;
}
