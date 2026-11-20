"use client";
import { useCallback, useEffect, useState } from "react";
import { useSession } from "@/lib/session-context";
import { Alert, Button, Input } from "@/components/ui";
import {
  billing, LEVEL_COLOR, money, RESOURCE_LABEL,
  type Budget, type Invoice, type Plan, type Provider, type Subscription, type Usage,
} from "@/lib/billing";

export default function BillingPage() {
  const { can, current } = useSession();
  const manage = can("billing:manage");
  const [sub, setSub] = useState<Subscription | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [budget, setBudget] = useState<Budget | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [confirm, setConfirm] = useState<Plan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setError(null);
    Promise.all([billing.subscription(), billing.plans(), billing.usage(), billing.budget(), billing.invoices(), billing.providers()])
      .then(([s, p, u, b, i, pr]) => { setSub(s); setPlans(p); setUsage(u); setBudget(b); setInvoices(i.items); setProviders(pr); })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load, current.organization.id]);

  const doChange = async () => {
    if (!confirm) return;
    setBusy(true);
    try {
      const r = await billing.change(confirm.code);
      setNote(`Switched to ${r.subscription.plan.name}.${r.invoice ? ` Invoice ${r.invoice.number}: ${money(r.invoice.total)}.` : ""}`);
      setConfirm(null); load();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const pay = async (inv: Invoice, provider: string) => {
    try {
      const p = await billing.pay(inv.id, provider);
      if (p.checkout_url) { window.location.assign(p.checkout_url); return; } // hosted Stripe / Razorpay checkout
      setNote(`Payment ${p.status}${p.simulated ? " (SIMULATED - no money moved)" : ""}`); load();
    }
    catch (e) { setError((e as Error).message); }
  };
  useEffect(() => {
    const r = new URLSearchParams(window.location.search).get("payment");
    if (r === "success") setNote("Payment submitted. The invoice is marked paid once the provider confirms it (usually within a minute).");
    if (r === "cancelled") setNote("Checkout cancelled. The invoice is still open.");
  }, []);
  const saveBudget = async () => {
    if (!budget) return;
    try {
      setBudget(await billing.saveBudget({
        monthly_limit: budget.monthly_limit === "" ? null : budget.monthly_limit, alert_thresholds: budget.alert_thresholds,
        hard_stop: budget.hard_stop, paid_fallback_enabled: budget.paid_fallback_enabled,
      }));
      setNote("Budget saved");
    } catch (e) { setError((e as Error).message); }
  };
  const payable = providers.filter((p) => p.status === "simulated" || p.status === "configured");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Billing</h1>
        <p className="mt-1 text-sm text-muted">Plan, usage, budget and invoices. Payments are simulated unless a provider is configured.</p>
      </div>
      {error && <Alert>{error}</Alert>}
      {note && <div className="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">{note}</div>}

      {sub && (
        <div className="card flex flex-wrap items-center justify-between gap-4 p-5">
          <div>
            <div className="text-xs text-muted">Current plan</div>
            <div className="text-2xl font-semibold">{sub.plan.name}</div>
            <div className="mt-1 text-sm text-muted">
              {money(sub.plan.price_monthly)} / month · <span className="capitalize">{sub.status.replace("_", " ")}</span>
              {sub.trial_end && sub.status === "trialing" && ` · trial ends ${new Date(sub.trial_end).toLocaleDateString()}`}
              {sub.status !== "trialing" && ` · renews ${new Date(sub.current_period_end).toLocaleDateString()}`}
            </div>
          </div>
          {sub.status === "past_due" && <Alert>Your trial has ended or a payment is due. Choose a plan or pay the open invoice.</Alert>}
        </div>
      )}

      {usage && (
        <div className="card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-medium">Usage · {usage.period}</h2>
            <span className="text-sm text-muted">Metered cost {money(usage.total_cost)}</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {usage.items.map((u) => (
              <div key={u.resource}>
                <div className="flex justify-between text-xs">
                  <span>{RESOURCE_LABEL[u.resource] ?? u.resource}</span>
                  <span className="text-muted">{u.used.toLocaleString()} / {u.limit == null ? "∞" : u.limit.toLocaleString()}</span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-raised">
                  <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(u.percent ?? 0, 100)}%`, background: LEVEL_COLOR[u.level] }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card p-5">
        <h2 className="mb-4 text-sm font-medium">Plans</h2>
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {plans.filter((p) => p.is_public).map((p) => {
            const isCurrent = sub?.plan.code === p.code && sub.status !== "past_due";
            return (
              <div key={p.id} className={`rounded-2xl border p-4 ${isCurrent ? "border-accent bg-accent-soft" : "border-line"}`}>
                <div className="font-medium">{p.name}</div>
                <div className="mt-1 text-xl font-semibold">{money(p.price_monthly)}<span className="text-xs font-normal text-muted">/mo</span></div>
                <ul className="mt-3 space-y-0.5 text-xs text-muted">
                  {["users", "leads", "voice_minutes", "workflows", "websites"].map((r) => (
                    <li key={r}>{p.limits[r] == null ? "Unlimited" : p.limits[r]!.toLocaleString()} {RESOURCE_LABEL[r]?.toLowerCase()}</li>
                  ))}
                </ul>
                {manage && !isCurrent && (
                  <Button variant="outline" className="mt-3 h-9 w-full" onClick={() => setConfirm(p)}>Choose</Button>
                )}
                {isCurrent && <div className="mt-3 text-center text-xs text-accent">Current plan</div>}
              </div>
            );
          })}
        </div>
        {confirm && (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-raised p-4 text-sm">
            <span>Switch to <b>{confirm.name}</b> ({money(confirm.price_monthly)}/mo)? Mid-period changes are prorated.</span>
            <span className="flex gap-2">
              <Button variant="ghost" className="h-9 px-4" onClick={() => setConfirm(null)}>Cancel</Button>
              <Button className="h-9 px-4" loading={busy} onClick={doChange}>Confirm</Button>
            </span>
          </div>
        )}
      </div>

      {budget && (
        <div className="card space-y-3 p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium">Monthly budget</h2>
            <span className="text-sm text-muted">Spent this month {money(budget.month_spend)}</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-xs text-muted">Monthly limit (USD, empty = none)
              <Input disabled={!manage} value={budget.monthly_limit ?? ""} onChange={(e) => setBudget({ ...budget, monthly_limit: e.target.value })} />
            </label>
            <label className="text-xs text-muted">Alert thresholds (%)
              <Input disabled={!manage} value={budget.alert_thresholds.join(", ")}
                onChange={(e) => setBudget({ ...budget, alert_thresholds: e.target.value.split(",").map((x) => parseInt(x, 10)).filter((x) => !Number.isNaN(x)) })} />
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" disabled={!manage} checked={budget.hard_stop} onChange={(e) => setBudget({ ...budget, hard_stop: e.target.checked })} />Hard stop when the limit is reached</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" disabled={!manage} checked={budget.paid_fallback_enabled} onChange={(e) => setBudget({ ...budget, paid_fallback_enabled: e.target.checked })} />Allow paid provider fallback</label>
          {manage && <Button className="h-9 px-4" onClick={saveBudget}>Save budget</Button>}
          {budget.alerts.length > 0 && (
            <ul className="space-y-1 text-xs">
              {budget.alerts.slice(0, 10).map((a) => (
                <li key={a.id} style={{ color: a.threshold >= 100 ? LEVEL_COLOR.exceeded : a.threshold >= 80 ? LEVEL_COLOR.critical : LEVEL_COLOR.warning }}>
                  {a.threshold}% of {a.kind === "budget" ? "budget" : RESOURCE_LABEL[a.resource] ?? a.resource} reached · {new Date(a.created_at).toLocaleDateString()}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="card p-5">
        <h2 className="mb-3 text-sm font-medium">Invoices</h2>
        {invoices.length === 0 ? <p className="text-sm text-muted">No invoices yet.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted"><tr><th className="py-2">Number</th><th>Date</th><th>Total</th><th>Status</th><th /></tr></thead>
              <tbody className="divide-y divide-line">
                {invoices.map((inv) => (
                  <tr key={inv.id}>
                    <td className="py-2">{inv.number}</td>
                    <td>{new Date(inv.created_at).toLocaleDateString()}</td>
                    <td>{money(inv.total, inv.currency)}</td>
                    <td className="capitalize">{inv.status}</td>
                    <td className="text-right">
                      {manage && inv.status === "open" && payable.map((p) => (
                        <Button key={p.name} variant="outline" className="ml-2 h-8 px-3 text-xs" onClick={() => pay(inv, p.name)}>Pay · {p.label}</Button>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
