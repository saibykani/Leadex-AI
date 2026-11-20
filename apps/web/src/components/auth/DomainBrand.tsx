"use client";
import { useEffect } from "react";
import { loadDomainBrand, useBrand } from "@/lib/branding";

/** On a white-label custom domain, shows the client's brand above the sign-in form. */
export function DomainBrand() {
  const brand = useBrand();
  useEffect(() => { void loadDomainBrand(); }, []);
  if (!brand?.app_name) return null;
  return (
    <div className="mb-5 flex items-center gap-2 text-lg font-semibold">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {brand.logo_url && <img src={brand.logo_url} alt="" className="h-8 w-8 rounded-lg object-contain" />}
      <span>{brand.app_name}</span>
    </div>
  );
}
