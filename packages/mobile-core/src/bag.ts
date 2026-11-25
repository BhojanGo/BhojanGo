// The customer's bag (P17): one restaurant, items with their option picks.
// Prices shown in the bag are indicative; the quote is what's charged.
import { create } from "zustand";

/** An option group as the menu API returns it. */
export interface OptionGroup {
  id: string;
  name: string;
  min_picks: number;
  max_picks: number;
  options: { id: string; name: string; price: string; is_default: boolean; is_available: boolean }[];
}

export interface Pick {
  group: string;
  option: string;
}

export interface BagLine {
  key: string; // item + picks, so the same dish with different picks is two lines
  menuItemId: string;
  name: string;
  unitPrice: number; // item price + option prices
  quantity: number;
  picks: Pick[];
  summary: string; // "Regular, medium, raita"
}

interface BagState {
  restaurantId: string | null;
  restaurantName: string | null;
  lines: BagLine[];
  tip: number;
  /** R36: delivery or pickup, chosen on the menu (the switch) or in the cart; a new cart starts at delivery. */
  fulfillment: "delivery" | "pickup";
  setFulfillment: (how: "delivery" | "pickup") => void;
  add: (restaurant: { id: string; name: string }, line: Omit<BagLine, "key">) => void;
  setQuantity: (key: string, quantity: number) => void;
  setTip: (tip: number) => void;
  clear: () => void;
  /** R43: the quote's prices replace the ones the cart kept (a price the restaurant changed since) */
  reprice: (prices: Record<string, number>) => void;
}

export type PriceChange = { key: string; name: string; was: number; now: number };

/** R43: dishes the quote prices differently from the cart (the restaurant changed a price since it was added).
 *  The quote lists the cart's dishes in the cart's order (the same request), with the dish + options price. */
export function priceChanges(lines: BagLine[], items: { menu_item_id: string; unit_price: string | number }[] | undefined): PriceChange[] {
  if (!items || items.length !== lines.length) return [];
  return lines.flatMap((l, i) => {
    const q = items[i]!;
    const now = Number(q.unit_price);
    return q.menu_item_id === l.menuItemId && Math.abs(now - l.unitPrice) > 0.004 ? [{ key: l.key, name: l.name, was: l.unitPrice, now }] : [];
  });
}

const keyOf = (id: string, picks: Pick[]) => `${id}|${picks.map((p) => `${p.group}=${p.option}`).sort().join(",")}`;

export const useBag = create<BagState>()((set) => ({
  restaurantId: null,
  restaurantName: null,
  lines: [],
  tip: 0,
  fulfillment: "delivery",
  setFulfillment: (fulfillment) => set({ fulfillment }),
  add: (restaurant, line) =>
    set((s) => {
      // A bag holds one restaurant: adding from another starts a new bag.
      const lines = s.restaurantId === restaurant.id ? s.lines : [];
      const key = keyOf(line.menuItemId, line.picks);
      const existing = lines.find((l) => l.key === key);
      return {
        restaurantId: restaurant.id,
        restaurantName: restaurant.name,
        lines: existing
          ? lines.map((l) => (l.key === key ? { ...l, quantity: l.quantity + line.quantity } : l))
          : [...lines, { ...line, key }],
      };
    }),
  setQuantity: (key, quantity) =>
    set((s) => {
      const lines = quantity <= 0 ? s.lines.filter((l) => l.key !== key) : s.lines.map((l) => (l.key === key ? { ...l, quantity } : l));
      return lines.length ? { lines } : { lines, restaurantId: null, restaurantName: null };
    }),
  setTip: (tip) => set({ tip }),
  clear: () => set({ restaurantId: null, restaurantName: null, lines: [], tip: 0, fulfillment: "delivery" }),
  reprice: (prices) => set((s) => ({ lines: s.lines.map((l) => (l.key in prices ? { ...l, unitPrice: prices[l.key]! } : l)) })),
}));

/** The cart lines for /pricing/quote and /orders. */
export function cartItems(lines: BagLine[]) {
  return lines.map((l) => ({ menu_item_id: l.menuItemId, quantity: l.quantity, options: l.picks }));
}

/** Default picks for an item: each group's default (or first available) option where at least one is required. */
export function defaultPicks(groups: OptionGroup[]): Pick[] {
  const picks: Pick[] = [];
  for (const g of groups) {
    if (g.min_picks < 1) continue;
    const opt = g.options.find((o) => o.is_default && o.is_available) ?? g.options.find((o) => o.is_available);
    if (opt) picks.push({ group: g.name, option: opt.name });
  }
  return picks;
}
