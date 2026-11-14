// A rule version's state in words. Only the version running now is "Live"; an older
// one was "Replaced on <date>" (a newer version took over) or "Ended on <date>"
// (nothing replaced it, so the inherited rule applies again).
import type { Rule } from "./ops";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
const past = (iso: string | null | undefined, now: number) => !!iso && new Date(iso).getTime() <= now;

export function versionState(v: Rule, all: Rule[] = [], now: number = Date.now()): { key: string; label: string } {
  if (v.status === "published") {
    if (!past(v.effective_from, now)) return { key: "scheduled", label: `Starts ${day(v.effective_from)}` };
    if (past(v.effective_to, now)) {
      const successor = all.find((o) => o.version > v.version && o.status === "published"
        && new Date(o.effective_from).getTime() === new Date(v.effective_to!).getTime());
      return successor ? { key: "replaced", label: `Replaced on ${day(v.effective_to!)}` } : { key: "ended", label: `Ended on ${day(v.effective_to!)}` };
    }
    if (v.paused_at) return { key: "paused", label: "Paused" };
    return { key: "live", label: v.effective_to ? `Live until ${day(v.effective_to)}` : "Live" };
  }
  const words: Record<string, string> = {
    pending_approval: "Waiting for approval", draft: "Draft", rejected: "Sent back", superseded: "Replaced before it started",
  };
  return { key: v.status, label: words[v.status] ?? v.status };
}
