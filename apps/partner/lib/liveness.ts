// R27: is the tablet still receiving orders? Pure (no React Native): test/liveness.test.ts.
//
// The board hears about orders two ways: the kitchen's realtime socket (an event on every
// order change, a pong to every heartbeat) and polling GET /orders/restaurant/{id} as the
// fallback. The tablet is receiving orders while either one has worked within OFFLINE_AFTER_MS;
// past that, every Kitchen screen shows the red "Not receiving orders" banner and an alarm.

/** No socket message and no good poll for this long: the tablet says it isn't receiving orders. */
export const OFFLINE_AFTER_MS = 15000;
/** Poll this often while the socket is up (a fallback; the socket brings each change at once). */
export const POLL_WITH_SOCKET_MS = 12000;
/** The kitchen socket's ping (the server answers "pong"; each ping is the tablet's heartbeat). */
export const SOCKET_HEARTBEAT_MS = 10000;
/** Poll this often while the socket is down. */
export const POLL_WITHOUT_SOCKET_MS = 4000;
/**
 * A refresh still running after this is treated as lost and another may start. Every request
 * already gives up on its own (a GET after 8 s, a token refresh after 15 s); this is the guard
 * against anything that still doesn't settle.
 */
export const STUCK_AFTER_MS = 45000;

export interface Link {
  /** When this board started watching (a fresh start gets OFFLINE_AFTER_MS before the banner). */
  since: number;
  /** The last poll that answered. */
  lastPoll: number | null;
  /** The last message on the socket (an event or a pong). */
  lastSocket: number | null;
}

/** The last time anything showed the tablet is connected. */
export function lastHeard(l: Link): number {
  return Math.max(l.since, l.lastPoll ?? 0, l.lastSocket ?? 0);
}

/** No socket and no successful poll for more than OFFLINE_AFTER_MS. */
export function isOffline(l: Link, now: number, after = OFFLINE_AFTER_MS): boolean {
  return now - lastHeard(l) > after;
}

/** Is the socket alive (a message within OFFLINE_AFTER_MS)? A socket that went quiet is as good as closed. */
export function socketAlive(l: Link, now: number, after = OFFLINE_AFTER_MS): boolean {
  return l.lastSocket !== null && now - l.lastSocket <= after;
}

/** How often to poll now. */
export function pollEvery(l: Link, now: number): number {
  return socketAlive(l, now) ? POLL_WITH_SOCKET_MS : POLL_WITHOUT_SOCKET_MS;
}

/**
 * May a refresh start now? Not while one is running (two at once used to pile up behind a hung
 * one), unless that one has been running longer than STUCK_AFTER_MS.
 */
export function mayStart(runningSince: number | null, now: number, stuckAfter = STUCK_AFTER_MS): boolean {
  return runningSince === null || now - runningSince > stuckAfter;
}

/** Is a poll due: never polled, or the last start was `every` ago? */
export function pollDue(lastStart: number | null, now: number, every: number): boolean {
  return lastStart === null || now - lastStart >= every;
}

/**
 * The server's clock minus this tablet's, from a response's Date header (whole seconds) and when
 * the request went out and came back: an accept timer counts down on the server's time, so a
 * tablet whose clock is off still shows the real deadline. 0 when there is no usable header.
 */
export function clockSkew(dateHeader: string | null | undefined, sentAt: number, receivedAt: number): number {
  const server = dateHeader ? Date.parse(dateHeader) : NaN;
  if (!Number.isFinite(server)) return 0;
  // The header is truncated to the second: its middle is half a second later.
  return Math.round(server + 500 - (sentAt + receivedAt) / 2);
}

/**
 * The accept timer: seconds left until the server's deadline (accept_due_at), on server time.
 * null when the order has no deadline. Never below 0; at 0 the card says "Accept now" (the order
 * can still be accepted until the server's sweep cancels it, every 10 s), never "0:00".
 */
export function acceptLeft(dueAt: string | null | undefined, now: number, skew: number): number | null {
  if (!dueAt) return null;
  const due = Date.parse(dueAt);
  if (!Number.isFinite(due)) return null;
  return Math.max(0, Math.ceil((due - (now + skew)) / 1000));
}

/** "2:05": minutes and seconds left (only for more than 0 seconds). */
export function mmss(seconds: number): string {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/**
 * R28: the note after customers couldn't order because this tablet wasn't connected. A gap that
 * starts and ends on the same minute said "from 2:50 pm to 2:50 pm": it is "for a few seconds".
 * `clock` writes a time as the board does (the kitchen's city, the app's language).
 */
export function offlineGapNote(from: string, to: string, clock: (iso: string) => string): { key: string; values?: Record<string, string> } {
  const a = clock(from);
  const b = clock(to);
  return a === b ? { key: "partner.orders.offline_gap_brief" } : { key: "partner.orders.offline_gap", values: { from: a, to: b } };
}
