import * as React from "react";
import { cn } from "../lib/utils";

/** Order statuses (P11 names) and how a customer reads them. */
export const ORDER_STATUS: Record<string, { label: string; tone: "wait" | "go" | "done" | "stop" }> = {
  pending_payment: { label: "Waiting for payment", tone: "wait" },
  placed: { label: "Placed", tone: "wait" },
  accepted: { label: "Accepted", tone: "go" },
  preparing: { label: "Cooking", tone: "go" },
  almost_ready: { label: "Almost ready", tone: "go" },
  ready: { label: "Ready for pickup", tone: "go" },
  picked_up: { label: "On the way", tone: "go" },
  delivered: { label: "Delivered", tone: "done" },
  cancelled: { label: "Cancelled", tone: "stop" },
};

const tones = {
  wait: "bg-porcelain text-kohl border border-line",
  go: "bg-peacock-tint text-peacock-deep",
  done: "bg-kohl text-white",
  stop: "bg-white text-chili border border-chili",
};

export function StatusPill({ status, label, className }: { status: string; label?: string; className?: string }) {
  const s = ORDER_STATUS[status] ?? { label: status, tone: "wait" as const };
  return (
    <span className={cn("inline-flex h-7 items-center self-start rounded-pill px-3 text-xs font-bold", tones[s.tone], className)}>
      {label ?? s.label}
    </span>
  );
}
