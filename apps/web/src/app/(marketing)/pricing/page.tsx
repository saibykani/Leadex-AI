import type { Metadata } from "next";
import { PricingView } from "@/components/marketing/pricing";

export const metadata: Metadata = { title: "Pricing | Leadex AI", description: "Leadex AI plans, real product limits, a transparent revenue estimator and answers to common questions." };

export default function Page() {
  return <PricingView />;
}
