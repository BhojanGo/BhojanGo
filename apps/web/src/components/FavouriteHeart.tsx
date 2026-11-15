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
  load: (userId: string) => Promise<void>;
  toggle: (kind: Kind, id: string) => Promise<void>;
}

export const useFavourites = create<Favs>((set, get) => ({
  loaded: null,
  ids: new Set(),
  load: async (userId) => {
    if (get().loaded === userId) return;
    set({ loaded: userId });
    try {
      const f = await authed<{ restaurants: { id: string }[]; items: { id: string }[] }>("GET", "/api/v1/me/favourites");
      set({ ids: new Set([...f.restaurants.map((r) => `restaurant:${r.id}`), ...f.items.map((i) => `item:${i.id}`)]) });
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
    set({ ids: next }); // optimistic
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
      className="flex items-center justify-center rounded-full bg-white shadow-[0_1px_3px_rgba(17,20,24,0.12)]"
    >
      <Heart filled={on} color={on ? "#C0392B" : "#111418"} />
    </button>
  );
}
