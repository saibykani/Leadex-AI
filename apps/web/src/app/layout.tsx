import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LEADEX AI",
  description: "Discover Opportunities. Engage Intelligently. Convert Businesses.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
