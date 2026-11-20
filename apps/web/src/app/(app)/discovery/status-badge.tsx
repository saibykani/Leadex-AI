export function StatusBadge({ status }: { status: string }) {
  const tone = status === "configured" || status === "available" || status === "completed" || status === "reachable"
    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : status === "not_configured" || status === "failed" || status === "unreachable_retry"
      ? "bg-amber-50 text-amber-700 border-amber-200"
      : "bg-raised text-muted border-line";
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${tone}`}>{status.replace(/_/g, " ")}</span>;
}
