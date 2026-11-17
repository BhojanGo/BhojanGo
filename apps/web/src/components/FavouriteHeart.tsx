"use client";
// The heart on kitchen cards and dishes: saves a favourite (signed in), or asks
// to sign in. The list of favourites is loaded once and shared.

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { create } from "zustand";

import { authed, useHydrated, useSession } from "@/lib/client";
import { useT } from "@/lib/i18n";
import { Heart } from "./Icons";

type Kind = "restaurant" | "item";

interface Favs {
  loaded: string | null; // the user id it was loaded for
  ids: Set<string>; // "restaurant:<id>" | "item:<id>"
  touched: Map<string, boolean>; // taps while the list was loading: they win over the loaded list
  load: (userId: string) => Promise<void>;
  toggle: (kind: Kind, id: string) => Promise<void>;
}

export const useFavourites = create<Favs>((set, get) => ({
  loaded: null,
  ids: new Set(),
  touched: new Map(),
  load: async (userId) => {
    if (get().loaded === userId) return;
    set({ loaded: userId, touched: new Map() });
    try {
      const f = await authed<{ restaurants: { id: string }[]; items: { id: string }[] }>("GET", "/api/v1/me/favourites");
      const ids = new Set([...f.restaurants.map((r) => `restaurant:${r.id}`), ...f.items.map((i) => `item:${i.id}`)]);
      for (const [key, on] of get().touched) {
        if (on) ids.add(key);
        else ids.delete(key);
      }
      set({ ids, touched: new Map() });
    } catch {
      set({ loaded: null });
    }
  },
  toggle: async (kind, id) => {
    const key = `${kind}:${id}`;
    const on = get().ids.has(key);
    const next = new Set(get().ids);
    if (on) next.delete(key);
    else next.add(key);
    set({ ids: next, touched: new Map(get().touched).set(key, !on) }); // optimistic
    try {
      await authed(on ? "DELETE" : "PUT", `/api/v1/me/favourites/${kind}/${id}`);
    } catch {
      const back = new Set(get().ids);
      if (on) back.add(key);
      else back.delete(key);
      set({ ids: back });
    }
  },
}));

export function FavouriteHeart({ kind, id, name, size = 36 }: { kind: Kind; id: string; name: string; size?: number }) {
  const t = useT();
  const hydrated = useHydrated();
  const user = useSession((s) => s.user);
  const router = useRouter();
  const path = usePathname();
  const { ids, load, toggle } = useFavourites();
  useEffect(() => {
    if (hydrated && user) void load(user.id);
  }, [hydrated, user, load]);
  const on = ids.has(`${kind}:${id}`);
  return (
    <button
      type="button"
      aria-pressed={on}
      aria-label={on ? t("common.unsave_kitchen", { name }) : t("common.save_kitchen", { name })}
      onClick={() => (user ? void toggle(kind, id) : router.push(`/signin?next=${encodeURIComponent(path)}`))}
      style={{ width: size, height: size }}
      className="relative flex items-center justify-center rounded-full bg-white shadow-[0_1px_3px_rgba(17,20,24,0.12)]"
    >
      {/* A 44 px touch target around a smaller heart (page checklist 7.4). */}
      {size < 44 && <span aria-hidden="true" className="absolute rounded-full" style={{ inset: -(44 - size) / 2 }} />}
      <Heart filled={on} color={on ? "#C0392B" : "#111418"} />
    </button>
  );
}
