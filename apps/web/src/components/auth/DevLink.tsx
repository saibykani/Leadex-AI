/** Shown only when the API reports the email as simulated (non-production): lets you test the flow locally. */
export function DevLink({ link }: { link: string | null | undefined }) {
  if (!link) return null;
  return (
    <div className="rounded-2xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
      <strong>Simulated email (development).</strong> No email was sent. Open the link it would contain:
      <a href={link} className="mt-1 block break-all font-mono text-[#0a6fd6] underline">{link}</a>
    </div>
  );
}
