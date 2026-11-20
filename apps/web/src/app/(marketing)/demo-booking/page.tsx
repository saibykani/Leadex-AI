import type { Metadata } from "next";
import { DemoBookingView } from "@/components/marketing/connect";

export const metadata: Metadata = { title: "Book a demo | Leadex AI", description: "Pick a time for a live Leadex AI walkthrough." };

export default function Page() {
  return <DemoBookingView />;
}
