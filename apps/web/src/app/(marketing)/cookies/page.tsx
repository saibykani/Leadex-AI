import type { Metadata } from "next";
import { CookiePolicy } from "@/components/marketing/legal";

export const metadata: Metadata = { title: "Cookie Policy | Leadex AI" };

export default function Page() {
  return <CookiePolicy />;
}
