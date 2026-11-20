import type { Metadata } from "next";
import { ConnectView } from "@/components/marketing/connect";

export const metadata: Metadata = { title: "Connect with the team | Leadex AI", description: "Talk to sales, book a demo, partnerships and support." };

export default function Page() {
  return <ConnectView />;
}
