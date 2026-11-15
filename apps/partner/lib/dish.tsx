// A dish exactly as customers see it on the kitchen's menu (the website's
// KitchenMenu row, apps/web/src/app/[country]/[city]/[kitchen]/KitchenMenu.tsx):
// veg mark, name, price in the country's currency, description, and the photo on
// the right with the Add button over its bottom edge; with no photo, a text-only
// row with the Add button at the end. The partner app shows it as the live
// preview while a kitchen changes a dish's photo.
import { num, type, useI18n } from "@bhojango/mobile-core";
import { Image, StyleSheet, Text, View } from "react-native";
import Svg, { Path } from "react-native-svg";

import { color, radius } from "./ui";

// The website's veg marks and muted tones (KitchenMenu.tsx).
const VEG = "#2E7D32";
const NON_VEG = "#8C1D18";
const LINE = "#E2E7E8";
const MUTED = "#4C5A5E";

export interface DishLook {
  name: string;
  /** Formatted in the country's currency (useFormat().cash). */
  price: string;
  description?: string | null;
  is_veg?: boolean;
  /** A photo the tablet can load (a picked file, or lib/data imageUri()); null: the text-only row. */
  photo: string | null;
  /** The dish has a photo the tablet can't load (a website photo-library path): show a stand-in. */
  photoElsewhere?: boolean;
  soldOut?: boolean;
}

function VegMark({ veg }: { veg?: boolean }) {
  const { t } = useI18n();
  if (veg === undefined) return null;
  const c = veg ? VEG : NON_VEG;
  return (
    <View accessibilityLabel={veg ? t("common.veg") : t("common.non_veg")} style={[s.veg, { borderColor: c }]}>
      {veg ? <View style={[s.vegDot, { backgroundColor: c }]} /> : (
        <Svg width={8} height={7} viewBox="0 0 8 7"><Path d="M4 0 8 7H0z" fill={c} /></Svg>
      )}
    </View>
  );
}

function AddButton() {
  const { t } = useI18n();
  return (
    <View style={s.add}>
      <Text style={[type.label, { color: color.peacock }]}>{t("common.add")}</Text>
    </View>
  );
}

export function DishPreview({ dish, testID }: { dish: DishLook; testID?: string }) {
  const { t } = useI18n();
  const pic = !!dish.photo || !!dish.photoElsewhere;
  return (
    <View testID={testID} style={[s.row, pic ? s.rowPic : s.rowText, dish.soldOut && { opacity: 0.6 }]}
      accessibilityLabel={t("partner.photo.preview_label", { name: dish.name })}>
      <View style={{ flex: 1, minWidth: 0 }}>
        <VegMark veg={dish.is_veg} />
        <Text style={[type.h3, s.name]}>{dish.name}</Text>
        <Text style={[type.label, num, s.price]}>{dish.price}</Text>
        {dish.description ? <Text style={[type.small, s.desc]}>{dish.description}</Text> : null}
        {dish.soldOut ? <Text style={[type.label, { marginTop: 8, color: NON_VEG }]}>{t("kitchen.sold_out_today")}</Text> : null}
      </View>
      {pic ? (
        <View style={s.photoBox}>
          <View style={s.photoClip}>
            {dish.photo ? (
              <Image testID="preview-photo" source={{ uri: dish.photo }} style={StyleSheet.absoluteFill} resizeMode="cover" />
            ) : (
              <View testID="preview-photo-elsewhere" style={[StyleSheet.absoluteFill, s.elsewhere]}>
                <Text style={[type.small, { color: MUTED, textAlign: "center" }]}>{t("partner.photo.library_photo")}</Text>
              </View>
            )}
          </View>
          <View style={s.addOver}><AddButton /></View>
        </View>
      ) : (
        <AddButton />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: "row", gap: 16, borderBottomWidth: 1, borderBottomColor: LINE, backgroundColor: color.white },
  rowPic: { paddingTop: 22, paddingBottom: 30 },
  rowText: { alignItems: "center", paddingVertical: 22 },
  veg: { width: 14, height: 14, borderWidth: 1.5, borderRadius: 3, alignItems: "center", justifyContent: "center" },
  vegDot: { width: 6, height: 6, borderRadius: 3 },
  name: { marginTop: 8, color: color.kohl },
  price: { marginTop: 4, color: color.kohl },
  desc: { marginTop: 8, color: MUTED },
  photoBox: { width: 112, height: 104 },
  photoClip: { width: 112, height: 104, borderRadius: radius.card, overflow: "hidden", backgroundColor: "#EFF6F6" },
  elsewhere: { alignItems: "center", justifyContent: "center", padding: 8 },
  addOver: { position: "absolute", bottom: -18, left: 0, right: 0, alignItems: "center" },
  add: {
    height: 40, paddingHorizontal: 22, borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.peacock, backgroundColor: color.white,
    alignItems: "center", justifyContent: "center",
    shadowColor: "#111418", shadowOpacity: 0.12, shadowRadius: 8, shadowOffset: { width: 0, height: 6 }, elevation: 3,
  },
});
