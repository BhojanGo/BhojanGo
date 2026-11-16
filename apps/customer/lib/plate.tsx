// Photos as the website shows them (R8): a kitchen's photo_url (its own cover,
// else its first dish photo, else a photo of its cuisine from the food library:
// core_api catalog.service.photos), else a plain branded tile (brand tint and a
// plate glyph, no text, so nothing is drawn over the kitchen's name); a dish's
// own photo, else no frame at all (the row is clean text). A photo that fails to
// load falls back the same way.
import { color } from "@bhojango/mobile-core";
import { useState, type ReactNode } from "react";
import { Image, View, type StyleProp, type ViewStyle } from "react-native";
import Svg, { Circle, Path } from "react-native-svg";

import { photoUrl } from "./contract";

/** photo_url, falling back to cover_url for an older API. */
export function kitchenPhoto(k: { photo_url?: string | null; cover_url?: string | null } | null | undefined): string | null {
  return k?.photo_url ?? k?.cover_url ?? null;
}

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

/** A kitchen with no photo at all: the brand tint and a plate glyph, no text. */
export function BrandTile({ width, height, rounded = 0 }: { width?: number | `${number}%`; height: number; rounded?: number }) {
  const glyph = Math.min(56, Math.round(height * 0.42));
  return (
    <View
      testID="kitchen-tile"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={{ width, height, borderRadius: rounded, backgroundColor: color.peacockTint, alignItems: "center", justifyContent: "center" }}
    >
      <Svg width={glyph} height={glyph} viewBox="0 0 48 48" fill="none" stroke={color.peacock} strokeOpacity={0.55} strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
        <Circle cx={24} cy={24} r={12} />
        <Circle cx={24} cy={24} r={7} strokeOpacity={0.35} />
        <Path d="M6 10v9a3 3 0 0 0 6 0v-9M9 10v28M42 10c-4 3-4 11 0 14v14" />
      </Svg>
    </View>
  );
}

/** A kitchen's picture (pass kitchenPhoto(k)), else the branded tile. */
export function KitchenCover({ name, cover, height, rounded = 0, width = 800 }: {
  name: string;
  cover: string | null | undefined;
  height: number;
  rounded?: number;
  width?: 400 | 800 | 1600;
}) {
  const tile = <BrandTile height={height} rounded={rounded} />;
  return <Photo uri={photo(cover, width)} label={name} style={{ height, borderRadius: rounded }} fallback={tile} testID="kitchen-photo" />;
}

/** A small square photo for rows (order again, favourites); the branded tile when there is none. */
export function Thumb({ name, uri, size = 52 }: { name: string; uri: string | null | undefined; size?: number }) {
  const tile = <BrandTile width={size} height={size} rounded={12} />;
  return <Photo uri={photo(uri, 400)} label={name} style={{ width: size, height: size, borderRadius: 12 }} fallback={tile} />;
}
