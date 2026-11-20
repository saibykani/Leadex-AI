import type { Metadata } from "next";
import { IndustriesPage } from "@/components/marketing/pages";

export const metadata: Metadata = { title: "Industries | Leadex AI", description: "Leadex AI for real estate, architects, construction, restaurants, clinics and more." };

export default function Page() {
  return <IndustriesPage />;
}
