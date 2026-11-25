// R42: is core_api answering? The API client says so after each call (lib/api.ts); the console shows a
// "can't reach BhojanGo" banner while it isn't, so an empty or half-loaded page is never read as the real state
// ("No live restaurants here yet", "You can't see this part of BhojanGo" when the server was simply down).
import { useSyncExternalStore } from "react";

let down = false;
const listeners = new Set<() => void>();

export function setApiReachable(reachable: boolean): void {
  if (down === !reachable) return;
  down = !reachable;
  listeners.forEach((l) => l());
}

/** True when the last call to core_api got no answer (or the gateway's "it's down" answer). */
export function useApiDown(): boolean {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => down,
    () => false,
  );
}

/** A failed call that means "the server isn't there", not "the server said no". */
export function unreachable(error: unknown): boolean {
  const r = (error as { response?: { status?: number; headers?: Record<string, string> } }).response;
  if (!r) return true;
  if (r.status === 502 || r.status === 503 || r.status === 504) return true;
  // The console's /api rewrite answers 500 with an HTML page when core_api is gone (core_api's own 500s are JSON)
  return r.status === 500 && !String(r.headers?.["content-type"] ?? "").includes("json");
}
