"use client";
import clsx from "clsx";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type ComponentType } from "react";
import { AnimatePresence, LayoutGroup, motion } from "framer-motion";
import {
  Palette,
  BarChart3, Bot, Building2, Check, ChevronDown, ChevronsLeft, Coins, CreditCard, Crown, FlaskConical, Gift, Globe2, Handshake,
  Keyboard, LayoutDashboard, LineChart, LogOut, Mail, Megaphone, Menu, MessageCircle, Phone, Plug, Plus, Rocket, Search, Settings,
  ShieldCheck, Sparkles, Lock, Users, Workflow, X,
} from "lucide-react";
import { auth } from "@/lib/api";
import { SessionProvider, useSession } from "@/lib/session-context";
import { Logo, PageTransition, ThemeProvider, ToastProvider } from "@/components/ui";
import { BillingNotice } from "@/components/billing-notice";
import { CommandPaletteProvider, useCommandPalette, type NavEntry } from "@/components/premium/command-palette";
import {
  DemoBanner, NotificationBell, ShortcutsDialog, ThemeToggle, popover, useGlobalShortcuts, useOutside,
} from "@/components/premium/shell-widgets";

type Item = { href: string; label: string; icon: ComponentType<{ className?: string }>; perm?: string; superadmin?: boolean; badge?: string };
const GROUPS: { title: string; items: Item[] }[] = [
  { title: "Overview", items: [
    { href: "/dashboard", label: "Command Center", icon: LayoutDashboard },
    { href: "/copilot", label: "Copilot", icon: Sparkles, perm: "leads:read", badge: "AI" },
    { href: "/insights", label: "Insights", icon: LineChart, perm: "leads:read" },
    { href: "/analytics", label: "Analytics", icon: BarChart3, perm: "leads:read" },
  ] },
  { title: "Growth", items: [
    { href: "/discovery", label: "Discovery", icon: Search, perm: "businesses:read" },
    { href: "/leads", label: "Leads", icon: Users, perm: "leads:read" },
    { href: "/pipeline", label: "Pipeline", icon: Workflow, perm: "businesses:read" },
    { href: "/campaigns", label: "Campaigns", icon: Megaphone },
  ] },
  { title: "AI", items: [
    { href: "/agents", label: "Voice Agents", icon: Bot, perm: "agents:read" },
    { href: "/calls", label: "Calls", icon: Phone, perm: "agents:read" },
    { href: "/websites", label: "Website Studio", icon: Globe2 },
  ] },
  { title: "Engage", items: [
    { href: "/email", label: "Email", icon: Mail },
    { href: "/whatsapp", label: "WhatsApp", icon: MessageCircle },
  ] },
  { title: "Marketplace", items: [
    { href: "/marketplace", label: "Marketplace", icon: Handshake },
    { href: "/referrals", label: "Referrals", icon: Gift },
    { href: "/commissions", label: "Commissions", icon: Coins },
  ] },
  { title: "Automation", items: [{ href: "/workflows", label: "Workflows", icon: Workflow }] },
  { title: "Admin", items: [
    { href: "/onboarding", label: "Get started", icon: Rocket },
    { href: "/demo", label: "Investor demo", icon: FlaskConical },
    { href: "/compliance", label: "Compliance", icon: ShieldCheck },
    { href: "/integrations", label: "Integrations", icon: Plug, perm: "integrations:manage" },
    { href: "/billing", label: "Billing", icon: CreditCard, perm: "billing:manage" },
    { href: "/settings", label: "Organization", icon: Settings },
    { href: "/settings/security", label: "Security", icon: Lock },
    { href: "/settings/branding", label: "Branding", icon: Palette, perm: "org:write" },
    { href: "/admin", label: "Super Admin", icon: Crown, superadmin: true },
  ] },
];
const ALL_HREFS = GROUPS.flatMap((g) => g.items.map((i) => i.href));
// Longest matching href wins so /settings/security doesn't also highlight /settings.
function activeHref(path: string) {
  return ALL_HREFS.filter((h) => path === h || path.startsWith(h + "/")).sort((a, b) => b.length - a.length)[0];
}

function useVisibleGroups() {
  const { me, can } = useSession();
  return GROUPS.map((g) => ({ ...g, items: g.items.filter((i) => (i.superadmin ? me.user.is_superadmin : !i.perm || can(i.perm))) }))
    .filter((g) => g.items.length);
}

function Sidebar({ onNavigate, collapsed = false, onToggle }: { onNavigate?: () => void; collapsed?: boolean; onToggle?: () => void }) {
  const path = usePathname();
  const active = activeHref(path);
  const groups = useVisibleGroups();
  const { open } = useCommandPalette();
  return (
    <div className="flex h-full flex-col">
      <div className={clsx("flex h-16 shrink-0 items-center", collapsed ? "justify-center" : "justify-between px-5")}>
        <Link href="/dashboard" onClick={onNavigate} aria-label="LeadexAI home" className="rounded-lg focus-ring"><Logo compact={collapsed} /></Link>
        {onToggle && !collapsed && (
          <button onClick={onToggle} aria-label="Collapse sidebar" title="Collapse sidebar ( [ )" className="rounded-lg p-1.5 text-muted transition hover:bg-raised hover:text-ink focus-ring">
            <ChevronsLeft className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className={clsx("pb-3", collapsed ? "px-3" : "px-3")}>
        <button onClick={open} aria-label="Search" title="Search (Ctrl K)"
          className={clsx("flex h-10 w-full items-center gap-2 rounded-xl border border-line bg-raised/60 text-sm text-muted transition hover:border-accent/30 hover:text-ink focus-ring",
            collapsed ? "justify-center" : "px-3")}>
          <Search className="h-4 w-4 shrink-0" />
          {!collapsed && <><span className="flex-1 text-left">Search…</span><kbd className="kbd">Ctrl K</kbd></>}
        </button>
      </div>
      <LayoutGroup id="sidebar">
        <nav aria-label="Main" className="flex-1 space-y-4 overflow-y-auto overflow-x-hidden px-3 pb-6">
          {groups.map((g) => (
            <div key={g.title}>
              {collapsed ? <div className="mx-auto mb-1.5 h-px w-6 bg-line" /> : <div className="eyebrow px-3 pb-1.5 text-neutral-400">{g.title}</div>}
              <div className="space-y-0.5">
                {g.items.map(({ href, label, icon: Icon, badge }) => {
                  const on = href === active;
                  return (
                    <Link key={href} href={href} onClick={onNavigate} title={collapsed ? label : undefined} aria-current={on ? "page" : undefined}
                      className={clsx("group relative flex items-center rounded-xl py-2 text-[14px] transition-colors focus-ring",
                        collapsed ? "justify-center px-0" : "gap-3 px-3",
                        on ? "font-medium text-ink" : "text-muted hover:bg-raised hover:text-ink")}>
                      {on && <motion.span layoutId="nav-active" className="absolute inset-0 rounded-xl bg-accent/10 ring-1 ring-inset ring-accent/15" transition={{ type: "spring", damping: 32, stiffness: 420 }} />}
                      {on && <motion.span layoutId="nav-bar" className="absolute -left-3 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-brand" transition={{ type: "spring", damping: 32, stiffness: 420 }} />}
                      <Icon className={clsx("relative h-[18px] w-[18px] shrink-0 transition-transform duration-200 group-hover:scale-110", on && "text-accent")} />
                      {!collapsed && <span className="relative flex-1 truncate">{label}</span>}
                      {!collapsed && badge && <span className="relative rounded-full bg-brand px-1.5 py-px text-[10px] font-bold text-white">{badge}</span>}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </LayoutGroup>
      {collapsed && onToggle && (
        <button onClick={onToggle} aria-label="Expand sidebar" className="mx-auto mb-4 rounded-lg p-2 text-muted hover:bg-raised hover:text-ink focus-ring">
          <ChevronsLeft className="h-4 w-4 rotate-180" />
        </button>
      )}
    </div>
  );
}

function OrgSwitcher() {
  const { me, current, switchOrg } = useSession();
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const ref = useOutside(open, close);
  const initial = current.organization.name.trim()[0]?.toUpperCase() ?? "W";
  return (
    <div ref={ref} className="relative min-w-0">
      <button onClick={() => setOpen((o) => !o)} aria-haspopup="listbox" aria-expanded={open}
        className="flex h-10 max-w-[260px] items-center gap-2 rounded-full border border-line bg-surface pl-1.5 pr-3 text-sm transition hover:-translate-y-px hover:border-accent/30 hover:shadow-card focus-ring">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand text-xs font-bold text-white">{initial}</span>
        <span className="truncate font-medium">{current.organization.name}</span>
        <ChevronDown className={clsx("h-4 w-4 shrink-0 text-muted transition-transform", open && "rotate-180")} />
      </button>
      <AnimatePresence>
        {open && (
          <motion.ul role="listbox" {...popover} className="glass absolute left-0 z-40 mt-2 w-72 rounded-2xl border border-line p-1.5 shadow-lift">
            <li className="eyebrow px-3 py-1.5">Workspaces</li>
            {me.memberships.map((m) => (
              <li key={m.organization.id}>
                <button onClick={() => { switchOrg(m.organization.id); setOpen(false); }}
                  className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm transition hover:bg-raised">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-raised text-xs font-semibold text-muted ring-1 ring-line"><Building2 className="h-3.5 w-3.5" /></span>
                  <span className="min-w-0 flex-1"><span className="block truncate">{m.organization.name}</span><span className="text-xs text-muted">{m.role}</span></span>
                  {m.organization.id === current.organization.id && <Check className="h-4 w-4 text-accent" />}
                </button>
              </li>
            ))}
            <li className="my-1 h-px bg-line" />
            <li><Link href="/demo" onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-muted transition hover:bg-raised hover:text-ink"><FlaskConical className="h-4 w-4" />Investor demo workspace</Link></li>
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}

function UserMenu({ onShortcuts }: { onShortcuts: () => void }) {
  const { me, current } = useSession();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const ref = useOutside(open, close);
  const initials = me.user.full_name.split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase() || "U";
  const item = "flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm transition hover:bg-raised";
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen((o) => !o)} aria-label="Account menu" aria-expanded={open}
        className="grid h-10 w-10 place-items-center rounded-full bg-brand text-sm font-semibold text-white shadow-sm ring-2 ring-surface transition hover:scale-105 hover:shadow-glow focus-ring">
        {initials}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div {...popover} className="glass absolute right-0 z-40 mt-2 w-64 rounded-2xl border border-line p-1.5 shadow-lift">
            <div className="px-3 py-2.5">
              <div className="truncate text-sm font-medium">{me.user.full_name}</div>
              <div className="truncate text-xs text-muted">{me.user.email}</div>
              <div className="mt-1 text-xs text-muted">{current.role}{me.user.is_superadmin && " · Super admin"}</div>
            </div>
            <div className="my-1 h-px bg-line" />
            <Link href="/settings/security" onClick={close} className={item}><Lock className="h-4 w-4 text-muted" />Security</Link>
            <Link href="/settings" onClick={close} className={item}><Settings className="h-4 w-4 text-muted" />Organization</Link>
            <button onClick={() => { close(); onShortcuts(); }} className={item}><Keyboard className="h-4 w-4 text-muted" /><span className="flex-1 text-left">Keyboard shortcuts</span><kbd className="kbd">?</kbd></button>
            <div className="my-1 h-px bg-line" />
            <button onClick={async () => { await auth.logout(); router.replace("/login"); }} className={clsx(item, "text-danger hover:bg-danger/5")}><LogOut className="h-4 w-4" />Sign out</button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function MobileNav({ onMenu }: { onMenu: () => void }) {
  const path = usePathname();
  const { open } = useCommandPalette();
  const { can } = useSession();
  const items = [
    { href: "/dashboard", label: "Home", icon: LayoutDashboard },
    ...(can("leads:read") ? [{ href: "/leads", label: "Leads", icon: Users }] : []),
    { href: "#search", label: "Search", icon: Search },
    ...(can("leads:read") ? [{ href: "/copilot", label: "Copilot", icon: Sparkles }] : []),
  ];
  return (
    <nav aria-label="Mobile" className="glass fixed inset-x-0 bottom-0 z-40 border-t border-line pb-[env(safe-area-inset-bottom)] md:hidden">
      <div className="mx-auto flex max-w-md items-stretch justify-around px-2">
        {items.map(({ href, label, icon: Icon }) => {
          const on = href !== "#search" && (path === href || path.startsWith(href + "/"));
          const cls = clsx("relative flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] font-medium transition-colors", on ? "text-accent" : "text-muted");
          const inner = (<>
            {on && <motion.span layoutId="mnav" className="absolute top-0 h-0.5 w-8 rounded-full bg-brand" />}
            {href === "#search"
              ? <span className="-mt-5 grid h-11 w-11 place-items-center rounded-full bg-brand text-white shadow-glow"><Icon className="h-5 w-5" /></span>
              : <Icon className="h-5 w-5" />}
            {label}
          </>);
          return href === "#search"
            ? <button key={href} onClick={open} aria-label="Search" className={cls}>{inner}</button>
            : <Link key={href} href={href} className={cls}>{inner}</Link>;
        })}
        <button onClick={onMenu} aria-label="Open menu" className="flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] font-medium text-muted"><Menu className="h-5 w-5" />More</button>
      </div>
    </nav>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const [mobile, setMobile] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const path = usePathname();
  const { current } = useSession();
  const { open } = useCommandPalette();
  useEffect(() => setMobile(false), [path]);
  useEffect(() => { try { setCollapsed(localStorage.getItem("lx_sidebar") === "1"); } catch { /* storage unavailable */ } }, []);
  const toggle = useCallback(() => setCollapsed((c) => {
    try { localStorage.setItem("lx_sidebar", c ? "0" : "1"); } catch { /* storage unavailable */ }
    return !c;
  }), []);
  const { help, setHelp } = useGlobalShortcuts(toggle);

  return (
    <div className="flex min-h-screen bg-bg">
      <motion.aside animate={{ width: collapsed ? 76 : 256 }} transition={{ type: "spring", damping: 32, stiffness: 320 }} initial={false}
        className="glass sticky top-0 hidden h-screen shrink-0 overflow-hidden border-r border-line lg:block">
        <Sidebar collapsed={collapsed} onToggle={toggle} />
      </motion.aside>
      <AnimatePresence>
        {mobile && (
          <motion.div className="fixed inset-0 z-50 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={() => setMobile(false)} />
            <motion.aside initial={{ x: -300 }} animate={{ x: 0 }} exit={{ x: -300 }} transition={{ type: "spring", damping: 30, stiffness: 300 }}
              className="absolute left-0 top-0 h-full w-72 border-r border-line bg-surface shadow-lift">
              <button onClick={() => setMobile(false)} aria-label="Close menu" className="absolute right-3 top-4 z-10 rounded-full p-2 text-muted hover:bg-raised"><X className="h-4 w-4" /></button>
              <Sidebar onNavigate={() => setMobile(false)} />
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="flex min-w-0 flex-1 flex-col">
        <DemoBanner />
        <header className="glass sticky top-0 z-30 flex h-16 items-center gap-2 border-b border-line px-3 sm:gap-3 sm:px-8">
          <button onClick={() => setMobile(true)} aria-label="Open menu" className="hidden rounded-full p-2 text-muted hover:bg-raised md:block lg:hidden"><Menu className="h-5 w-5" /></button>
          <OrgSwitcher />
          <button onClick={open} className="ml-2 hidden h-10 w-72 items-center gap-2 rounded-full border border-line bg-raised/60 px-4 text-sm text-muted transition hover:border-accent/30 hover:text-ink focus-ring xl:flex">
            <Search className="h-4 w-4" /><span className="flex-1 text-left">Search or jump to…</span><kbd className="kbd">Ctrl K</kbd>
          </button>
          <div className="ml-auto flex items-center gap-0.5 sm:gap-1">
            <Link href="/leads" aria-label="Quick add" title="Leads" className="hidden h-10 items-center gap-1.5 rounded-full bg-brand px-4 text-sm font-medium text-white shadow-glow transition hover:-translate-y-px hover:brightness-110 sm:flex">
              <Plus className="h-4 w-4" />New
            </Link>
            <ThemeToggle />
            <NotificationBell />
            <UserMenu onShortcuts={() => setHelp(true)} />
          </div>
        </header>
        {/* key on org forces pages to remount and refetch tenant data after switching orgs */}
        <main className="mx-auto w-full min-w-0 max-w-7xl flex-1 px-4 pb-28 pt-6 sm:px-8 sm:pt-8 md:pb-10">
          <PageTransition id={current.organization.id + path}>{children}</PageTransition>
        </main>
      </div>
      <MobileNav onMenu={() => setMobile(true)} />
      <ShortcutsDialog open={help} onClose={() => setHelp(false)} />
    </div>
  );
}

function Providers({ children }: { children: React.ReactNode }) {
  const groups = useVisibleGroups();
  const nav: NavEntry[] = groups.flatMap((g) => g.items.map((i) => ({ href: i.href, label: i.label, icon: i.icon as NavEntry["icon"], group: g.title })));
  return <CommandPaletteProvider nav={nav}>{children}</CommandPaletteProvider>;
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <SessionProvider>
        <ToastProvider>
          <Providers><Shell>{children}</Shell></Providers>
          <BillingNotice />
        </ToastProvider>
      </SessionProvider>
    </ThemeProvider>
  );
}
