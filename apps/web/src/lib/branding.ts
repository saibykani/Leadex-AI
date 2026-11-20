"use client";
// White label: the workspace's (or custom domain's) brand name, logo and colour, applied app-wide.
import { useEffect, useState } from "react";
import { api, API_URL } from "@/lib/api";

export type Brand = {
  app_name: string | null; logo_url: string | null; primary_color: string | null; support_email: string | null;
  app_domain: string | null; hide_powered_by: boolean;
};

let current: Brand | null = null;
const EVENT = "leadex:brand";

function rgb(hex: string): string | null {
  const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex);
  return m ? `${parseInt(m[1], 16)} ${parseInt(m[2], 16)} ${parseInt(m[3], 16)}` : null;
}

export function applyBrand(b: Brand | null) {
  current = b;
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  const c = b?.primary_color ? rgb(b.primary_color) : null;
  if (c) {
    root.style.setProperty("--c-accent", c);
    root.style.setProperty("--c-accent-strong", c);
  } else {
    root.style.removeProperty("--c-accent");
    root.style.removeProperty("--c-accent-strong");
  }
  if (b?.app_name) document.title = b.app_name;
  window.dispatchEvent(new Event(EVENT));
}

export function useBrand(): Brand | null {
  const [b, setB] = useState<Brand | null>(current);
  useEffect(() => {
    const on = () => setB(current);
    window.addEventListener(EVENT, on);
    return () => window.removeEventListener(EVENT, on);
  }, []);
  return b;
}

/** Signed-in workspace brand. */
export const loadWorkspaceBrand = () => api<Brand>("/branding", {}, true).then(applyBrand).catch(() => {});

/** Custom-domain brand for public pages such as sign-in (no auth). */
export async function loadDomainBrand() {
  if (typeof window === "undefined") return;
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1") return;
  try {
    const r = await fetch(`${API_URL}/api/v1/public/branding?domain=${encodeURIComponent(host)}`);
    if (r.ok) { const b: Brand = await r.json(); if (b.app_name || b.primary_color) applyBrand(b); }
  } catch { /* default brand */ }
}

export const brandingApi = {
  get: () => api<Brand>("/branding", {}, true),
  save: (b: Partial<Brand>) => api<Brand>("/branding", { method: "PUT", body: JSON.stringify(b) }, true),
};
