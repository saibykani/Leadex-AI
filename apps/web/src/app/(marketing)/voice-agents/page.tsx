import type { Metadata } from "next";
import { VoiceAgentsPage } from "@/components/marketing/pages";

export const metadata: Metadata = { title: "AI Voice Agents | Leadex AI", description: "AI voice agents that qualify, book and follow up, with disclosure built in." };

export default function Page() {
  return <VoiceAgentsPage />;
}
