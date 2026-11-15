// Photos as the website shows them: a kitchen's own cover, else its initials
// tile (brand tint, initials, first cuisine); a dish's own photo, else no frame
// at all (the row is clean text). Never another kitchen's photo, never an empty
// frame: a photo that fails to load falls back the same way.
import { color, type } from "@bhojango/mobile-core";
import { useState, type ReactNode } from "react";
import { Image, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { initials, photoUrl } from "./contract";

/** The website's address: library photos ("/food/...") are served from there (tools/mobile/env-profile.sh). */
export const WEB_URL: string = process.env.EXPO_PUBLIC_WEB_URL || "http://localhost:3000";

/** An API photo URL resolved for <Image> (null: show the no-photo form). */
export function photo(url: string | null | undefined, width: 400 | 800 | 1600 = 800): string | null {
  return photoUrl(url, WEB_URL, width);
}

/** A full-bleed photo; `fallback` (or nothing) when there is none or it fails to load. */
export function Photo({ uri, label, style, fallback = null, testID }: {
  uri: string | null;
  label?: string;
  style?: StyleProp<ViewStyle>;
  fallback?: ReactNode;
  testID?: string;
}) {
  const [failed, setFailed] = useState<string | null>(null);
  if (!uri || failed === uri) return <>{fallback}</>;
  return (
    <View style={[{ overflow: "hidden", backgroundColor: color.plate }, style]} testID={testID}>
      <Image
        source={{ uri }}
        accessibilityLabel={label}
        accessibilityIgnoresInvertColors
        resizeMode="cover"
        onError={() => setFailed(uri)}
        style={{ width: "100%", height: "100%" }}
      />
    </View>
  );
}

/** A kitchen with no photo of its own: its initials and first cuisine on the brand tint. */
export function NameTile({ name, sub, height, rounded = 0, size = "lg" }: {
  name: string;
  sub?: string | null;
  height: number;
  rounded?: number;
  size?: "sm" | "lg";
}) {
  const big = size === "lg";
  return (
    <View
      testID="kitchen-initials"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={{ height, borderRadius: rounded, backgroundColor: color.peacockTint, alignItems: "center", justifyContent: "center" }}
    >
      <Text style={[big ? type.display : type.h3, { color: color.peacockDeep }]}>{initials(name) || "·"}</Text>
      {sub && big ? (
        <Text numberOfLines={1} style={[type.caption, { marginTop: 6, color: color.peacock }]}>{sub}</Text>
      ) : null}
    </View>
  );
}

/** A kitchen's cover: its own photo, else its initials tile. */
export function KitchenCover({ name, cover, cuisine, height, rounded = 0, width = 800, size = "lg" }: {
  name: string;
  cover: string | null | undefined;
  cuisine?: string | null;
  height: number;
  rounded?: number;
  width?: 400 | 800 | 1600;
  size?: "sm" | "lg";
}) {
  const tile = <NameTile name={name} sub={cuisine} height={height} rounded={rounded} size={size} />;
  return <Photo uri={photo(cover, width)} label={name} style={{ height, borderRadius: rounded }} fallback={tile} testID="kitchen-photo" />;
}

/** A small square photo for rows (order again, favourites); the initials when there is none. */
export function Thumb({ name, uri, size = 52 }: { name: string; uri: string | null | undefined; size?: number }) {
  const tile = (
    <View style={{ width: size, height: size, borderRadius: 12, backgroundColor: color.peacockTint, alignItems: "center", justifyContent: "center" }}>
      <Text style={[size >= 72 ? type.h1 : size >= 48 ? type.h2 : type.h3, { color: color.peacockDeep }]}>{initials(name) || "·"}</Text>
    </View>
  );
  return <Photo uri={photo(uri, 400)} label={name} style={{ width: size, height: size, borderRadius: 12 }} fallback={tile} />;
}
