// The two lines on the tracking map (web LiveMap; the customer app's
// lib/route.ts is the same code): solid where the delivery partner has been on
// the leg the customer cares about, ending at the partner's live position, and
// dashed from the partner to the next stop (the kitchen, then home).
//
// Why a leg and not the whole trail (R8): realtime keeps every fix since the
// partner accepted the order (trail:{order}), so the trail starts wherever they
// were when the offer came, a kilometre or two from the kitchen in any direction, and runs to
// the kitchen before it heads home. Drawn as one line after pickup it left the
// kitchen the wrong way and ended in empty map (and the app drew a straight
// segment from the kitchen to that start). After pickup the solid line now starts
// at the kitchen, at the partner's last fix there, and the ride there is dropped.
// Pure functions, no map library: tested in test/route.test.ts.

export type Pt = [number, number]; // [lat, lng], as the tracking socket sends them

/** A fix this close to the kitchen counts as "at the kitchen" (GPS on a street is off by tens of metres). */
export const AT_KITCHEN_M = 150;

export function metresBetween(a: Pt, b: Pt): number {
  const rad = (d: number) => (d * Math.PI) / 180;
  const h = Math.sin(rad(b[0] - a[0]) / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(rad(b[1] - a[1]) / 2) ** 2;
  return 6371000 * 2 * Math.asin(Math.min(1, Math.sqrt(h)));
}

const valid = (p: Pt | null | undefined): p is Pt =>
  !!p && Number.isFinite(p[0]) && Number.isFinite(p[1]) && Math.abs(p[0]) <= 90 && Math.abs(p[1]) <= 180;
const same = (a: Pt, b: Pt) => a[0] === b[0] && a[1] === b[1];

/** The points in order without bad or repeated fixes (a parked partner sends the same fix again and again). */
function clean(points: readonly (Pt | null | undefined)[]): Pt[] {
  const out: Pt[] = [];
  for (const p of points) {
    if (!valid(p)) continue;
    const q: Pt = [p[0], p[1]];
    if (!out.length || !same(out[out.length - 1]!, q)) out.push(q);
  }
  return out;
}

/**
 * The part of the trail after the partner left the kitchen: the fixes after the
 * last one within AT_KITCHEN_M of it. When no fix is that close (the oldest fixes
 * were trimmed, or GPS was poor at the kitchen), the fixes from the one nearest
 * the kitchen on.
 */
export function sinceKitchen(trail: readonly Pt[], kitchen: Pt): Pt[] {
  let last = -1;
  let nearest = 0;
  let best = Infinity;
  trail.forEach((p, i) => {
    const d = metresBetween(p, kitchen);
    if (d <= AT_KITCHEN_M) last = i;
    if (d < best) {
      best = d;
      nearest = i;
    }
  });
  return last >= 0 ? trail.slice(last + 1) : trail.slice(nearest);
}

export interface RouteInput {
  pickup: Pt | null;
  dropoff: Pt | null;
  /** The partner's live position (null when there is none, or the order is over). */
  rider: Pt | null;
  /** Every fix since the partner accepted, oldest first. */
  trail: readonly Pt[];
  /** Where the partner goes next: the kitchen before pickup, home after; null when the order is over. */
  leg: "kitchen" | "home" | null;
}

export interface RouteLines {
  /** Solid: where the partner has been on this leg, ending at the partner. Empty or 2+ points. */
  done: Pt[];
  /** Dashed: from the partner to the next stop. Empty or exactly 2 points. */
  ahead: Pt[];
}

export function routeLines({ pickup, dropoff, rider, trail, leg }: RouteInput): RouteLines {
  const kitchen = valid(pickup) ? pickup : null;
  const home = valid(dropoff) ? dropoff : null;
  const fixes = clean(trail);
  const now = valid(rider) ? rider : null;

  let done: Pt[];
  if (leg === "kitchen") {
    // On the way to the kitchen: the ride so far (from where they accepted) to where they are.
    done = clean([...fixes, now]);
  } else {
    // Picked up (or over): from the kitchen, along the fixes since, to where they are.
    done = kitchen ? clean([kitchen, ...sinceKitchen(fixes, kitchen), now]) : clean([...fixes, now]);
  }
  if (done.length < 2) done = [];

  // Where the partner is: the live position, else the end of the solid line; just
  // after pickup with no fix yet, the kitchen (the way home starts there).
  const from = now ?? done[done.length - 1] ?? (leg === "home" ? kitchen : leg === "kitchen" ? (fixes[fixes.length - 1] ?? null) : null);
  const to = leg === "kitchen" ? kitchen : leg === "home" ? home : null;
  const ahead = from && to && !same(from, to) ? [from, to] : [];
  return { done, ahead };
}
