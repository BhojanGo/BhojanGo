// The heart on kitchen cards, the kitchen page and dishes: saves a favourite
// (PUT/DELETE /me/favourites/{kind}/{id}). The list is loaded once and shared.
import { color, useI18n } from "@bhojango/mobile-core";
import { useEffect } from "react";
import { Pressable } from "react-native";
import Svg, { Path } from "react-native-svg";

import { isFavourite, useFavourites, type FavKind } from "../lib/favourites";

const HEART = "M12 20s-7.5-4.6-9.2-9.4C1.6 7.2 3.9 4 7.2 4c2 0 3.6 1.1 4.8 2.8C13.2 5.1 14.8 4 16.8 4c3.3 0 5.6 3.2 4.4 6.6C19.5 15.4 12 20 12 20z";

export function HeartIcon({ on, size = 20 }: { on: boolean; size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill={on ? color.chili : "none"} stroke={on ? color.chili : color.kohl} strokeWidth={2} strokeLinejoin="round">
      <Path d={HEART} />
    </Svg>
  );
}

export function FavouriteHeart({ kind, id, name, size = 40, testID }: { kind: FavKind; id: string; name: string; size?: number; testID?: string }) {
  const { t } = useI18n();
  const ids = useFavourites((s) => s.ids);
  const load = useFavourites((s) => s.load);
  const toggle = useFavourites((s) => s.toggle);
  useEffect(() => {
    void load();
  }, [load]);
  const on = isFavourite(ids, kind, id);
  const label = on
    ? (kind === "restaurant" ? t("common.unsave_kitchen", { name }) : t("favourites.unsave_dish", { name }))
    : t("common.save_kitchen", { name });
  return (
    <Pressable
      testID={testID ?? `heart-${kind}-${id}`}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: on }}
      hitSlop={6}
      onPress={() => void toggle(kind, id)}
      style={{
        width: size, height: size, borderRadius: size / 2, backgroundColor: color.white, alignItems: "center", justifyContent: "center",
        shadowColor: color.kohl, shadowOpacity: 0.12, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 2,
      }}
    >
      <HeartIcon on={on} size={Math.round(size * 0.5)} />
    </Pressable>
  );
}
