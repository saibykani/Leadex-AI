import { STATUS_TONE } from "@/lib/communication";

export function Badge({ value }: { value: string }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_TONE[value] ?? "bg-neutral-100 text-neutral-700"}`}>
      {value.replace(/_/g, " ")}
    </span>
  );
}
