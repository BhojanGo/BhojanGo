// R17: which ordering pauses a page shows (the banner in components/OrderingPauseBanner.tsx).

export interface OrderingPause { id: string; scope: string; area: string; note?: string | null; until?: string | null }

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

export function shownPauses(pauses: OrderingPause[], path: string): OrderingPause[] {
  const [country, city] = path.split("/").filter(Boolean);
  if (!country || country.length !== 2) return pauses; // not a place page: every pause
  return pauses.filter((p) => p.scope === "*" || (p.scope.slice(0, 2) === country.toUpperCase()
    && (p.scope.length === 2 || !city || slug(p.area) === city)));
}
