// R28: the pure part of lib/location.ts (no native modules), for node --test.

/** How often an online partner's phone sends its position (time-based, even standing still). */
export const SEND_EVERY_MS = 5000;
/** No position reached BhojanGo for this long: "Location lost", and no offers (the server's window too). */
export const LOST_AFTER_MS = 60000;
/**
 * The background task's options version. A task already running from an older build keeps its old
 * options (R27/R28: distanceInterval 10 m sent nothing while standing still), so a different
 * version restarts it.
 */
export const TRACKING_OPTIONS_VERSION = "2";

/** Online, and the last position BhojanGo took is older than LOST_AFTER_MS (or none since going online). */
export function locationLost(online: boolean, lastSentAt: number | null, onlineSince: number | null, now: number): boolean {
  if (!online) return false;
  const since = lastSentAt ?? onlineSince;
  return since != null && now - since > LOST_AFTER_MS;
}
