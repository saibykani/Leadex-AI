import type { Metadata } from "next";
import { TermsOfService } from "@/components/marketing/legal";

export const metadata: Metadata = { title: "Terms of Service | Leadex AI" };

export default function Page() {
  return <TermsOfService />;
}
