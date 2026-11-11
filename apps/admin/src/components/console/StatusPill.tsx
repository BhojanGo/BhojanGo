import type { MarketStatus } from "@/lib/markets";

const STYLES: Record<MarketStatus, string> = {
  live: "bg-peacock-tint text-peacock-dark",
  beta: "bg-kesar-tint text-kesar-ink",
  paused: "bg-danger-tint text-danger-ink",
  draft: "bg-line-soft text-muted",
};

const LABELS: Record<MarketStatus, string> = { live: "Live", beta: "Beta", paused: "Paused", draft: "Draft" };

export function StatusPill({ status }: { status: MarketStatus }) {
  return (
    <span className={`inline-flex items-center rounded-lg px-2 py-1 text-xs font-bold ${STYLES[status]}`}>
      {LABELS[status]}
    </span>
  );
}
