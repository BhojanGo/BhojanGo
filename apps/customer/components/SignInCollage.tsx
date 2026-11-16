// The sign-in screen's food photos (R8, as the website's sign-in): they fill the
// room between the headline and the sign-in sheet, so a tall phone shows food
// instead of an empty middle. The photos are data: the country's hero dish
// (Markets) and its first live city's kitchens (GET /discover?city=). The grid
// takes whatever height is left (flex: 1): two rows when there is room, one row
// on a short phone, none when the keyboard or a taller sheet leaves almost nothing.
import { api, radius, unwrap, useCountry } from "@bhojango/mobile-core";
import { useEffect, useState } from "react";
import { View } from "react-native";

import { signInPhotos, type KitchenCard } from "../lib/contract";
import { BrandTile, photo, Photo } from "../lib/plate";

const GAP = 8;
const ONE_ROW_FROM = 96; // below this much height, no photos at all
const TWO_ROWS_FROM = 260;

export function SignInCollage() {
  const { country } = useCountry();
  const [kitchens, setKitchens] = useState<KitchenCard[]>([]);
  const [box, setBox] = useState<{ w: number; h: number } | null>(null);
  const city = country?.regions.flatMap((r) => r.cities).find((c) => c.status === "live")?.code ?? null;

  useEffect(() => {
    if (!city) return;
    let alive = true;
    api.core.GET("/api/v1/discover", { params: { query: { city } } })
      .then((r) => alive && setKitchens(((unwrap(r) as { restaurants?: KitchenCard[] }).restaurants) ?? []))
      .catch(() => undefined); // offline: the branded tiles stay
    return () => {
      alive = false;
    };
  }, [city]);

  const urls = signInPhotos(country?.hero_photo, kitchens, 4);
  const rows = !box || box.h < ONE_ROW_FROM ? 0 : box.h < TWO_ROWS_FROM ? 1 : 2;
  const tile = box && rows ? { w: (box.w - GAP) / 2, h: Math.min((box.h - GAP * (rows - 1)) / rows, (box.w - GAP) / 2 * 1.2) } : null;

  return (
    <View
      testID="sign-in-photos"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      onLayout={(e) => setBox({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })}
      style={{ flex: 1, minHeight: 0, flexDirection: "row", flexWrap: "wrap", alignContent: "center", gap: GAP, marginTop: 24, marginBottom: 20 }}
    >
      {tile
        ? Array.from({ length: rows * 2 }, (_, i) => {
            const fallback = <BrandTile width={tile.w} height={tile.h} rounded={radius.card} />;
            return (
              <View key={i} style={{ width: tile.w, height: tile.h }}>
                <Photo uri={photo(urls[i], 800)} style={{ width: tile.w, height: tile.h, borderRadius: radius.card }} fallback={fallback} />
              </View>
            );
          })
        : null}
    </View>
  );
}
