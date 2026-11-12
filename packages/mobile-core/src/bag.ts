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
  add: (restaurant: { id: string; name: string }, line: Omit<BagLine, "key">) => void;
  setQuantity: (key: string, quantity: number) => void;
  setTip: (tip: number) => void;
  clear: () => void;
}

const keyOf = (id: string, picks: Pick[]) => `${id}|${picks.map((p) => `${p.group}=${p.option}`).sort().join(",")}`;

export const useBag = create<BagState>()((set) => ({
  restaurantId: null,
  restaurantName: null,
  lines: [],
  tip: 0,
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
  clear: () => set({ restaurantId: null, restaurantName: null, lines: [], tip: 0 }),
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
