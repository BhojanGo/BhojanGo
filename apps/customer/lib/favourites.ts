// Favourites (GET/PUT/DELETE /me/favourites), shared by every heart on screen
// and the favourites list. Taps are optimistic; a failed save is put back.
import { api, unwrap, type CoreSchemas } from "@bhojango/mobile-core";
import { create } from "zustand";

export type Favourites = CoreSchemas["FavouritesOut"];
export type FavKind = "restaurant" | "item";

interface FavState {
  list: Favourites | null;
  ids: Set<string>; // "restaurant:<id>" | "item:<id>"
  loading: boolean;
  error: boolean;
  touched: Map<string, boolean>; // taps while the list was loading win over it
  load: (force?: boolean) => Promise<void>;
  toggle: (kind: FavKind, id: string) => Promise<void>;
  reset: () => void;
}

const keyOf = (kind: FavKind, id: string) => `${kind}:${id}`;

export const useFavourites = create<FavState>()((set, get) => ({
  list: null,
  ids: new Set(),
  loading: false,
  error: false,
  touched: new Map(),

  load: async (force = false) => {
    if (get().loading || (get().list && !force)) return;
    set({ loading: true, error: false });
    try {
      const f = unwrap(await api.core.GET("/api/v1/me/favourites")) as Favourites;
      const ids = new Set([...f.restaurants.map((r) => keyOf("restaurant", r.id)), ...f.items.map((i) => keyOf("item", i.id))]);
      for (const [key, on] of get().touched) {
        if (on) ids.add(key);
        else ids.delete(key);
      }
      set({ list: f, ids, loading: false, touched: new Map() });
    } catch {
      set({ loading: false, error: true });
    }
  },

  toggle: async (kind, id) => {
    const key = keyOf(kind, id);
    const on = get().ids.has(key);
    const next = new Set(get().ids);
    if (on) next.delete(key);
    else next.add(key);
    set({ ids: next, touched: new Map(get().touched).set(key, !on) });
    try {
      const path = { kind, target_id: id };
      if (on) unwrap(await api.core.DELETE("/api/v1/me/favourites/{kind}/{target_id}", { params: { path } }));
      else unwrap(await api.core.PUT("/api/v1/me/favourites/{kind}/{target_id}", { params: { path } }));
      // The list screen shows what's saved now (names, photos come from the API).
      if (get().list) void get().load(true);
    } catch {
      const back = new Set(get().ids);
      if (on) back.add(key);
      else back.delete(key);
      set({ ids: back });
    }
  },

  reset: () => set({ list: null, ids: new Set(), touched: new Map(), error: false }),
}));

export function isFavourite(ids: Set<string>, kind: FavKind, id: string): boolean {
  return ids.has(keyOf(kind, id));
}
