import type { Metadata } from "next";
import { PrivacyPolicy } from "@/components/marketing/legal";

export const metadata: Metadata = { title: "Privacy Policy | Leadex AI" };

export default function Page() {
  return <PrivacyPolicy />;
}
