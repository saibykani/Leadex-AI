import type { Metadata } from "next";
import { WebsiteStudioPage } from "@/components/marketing/pages";

export const metadata: Metadata = { title: "Website Studio | Leadex AI", description: "Generate industry-specific website previews from verified business details." };

export default function Page() {
  return <WebsiteStudioPage />;
}
