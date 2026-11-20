import type { Metadata } from "next";
import { DocsPage } from "@/components/marketing/pages";

export const metadata: Metadata = { title: "Docs | Leadex AI", description: "Guides for every Leadex AI module." };

export default function Page() {
  return <DocsPage />;
}
