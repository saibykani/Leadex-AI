"use client";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { auth, ensureSession, session, type Me, type Membership } from "@/lib/api";
import { loadWorkspaceBrand } from "@/lib/branding";

type Ctx = { me: Me; current: Membership; switchOrg: (id: string) => void; reload: () => Promise<void>; can: (p: string) => boolean };
const SessionCtx = createContext<Ctx | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [orgId, setOrgId] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const m = await auth.me();
      const stored = session.org;
      const pick = m.memberships.find((x) => x.organization.id === stored) ?? m.memberships[0];
      if (pick) session.setOrg(pick.organization.id);
      setOrgId(pick?.organization.id ?? null);
      setMe(m);
      void loadWorkspaceBrand();
    } catch {
      session.clear();
      router.replace("/login");
    }
  }, [router]);

  useEffect(() => {
    void ensureSession().then((ok) => (ok ? reload() : router.replace("/login")));
  }, [reload, router]);

  const current = me?.memberships.find((m) => m.organization.id === orgId);
  const can = useCallback((p: string) => !!current?.permissions.includes(p), [current]);
  if (!me || !current) {
    return <div className="flex min-h-screen items-center justify-center text-sm text-muted">Loading workspace…</div>;
  }
  const switchOrg = (id: string) => { session.setOrg(id); setOrgId(id); void loadWorkspaceBrand(); };
  return <SessionCtx.Provider value={{ me, current, switchOrg, reload, can }}>{children}</SessionCtx.Provider>;
}

export function useSession() {
  const c = useContext(SessionCtx);
  if (!c) throw new Error("useSession outside SessionProvider");
  return c;
}
