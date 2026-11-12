// A dish or kitchen on the plate frame, with an optional dark badge on top.
import { color, PlateImage, radius, textFont } from "@bhojango/mobile-core";
import { Text, View } from "react-native";

export function PlateHeader({ label, height = 118, size, badge, uri }: {
  label: string;
  height?: number;
  size?: number;
  badge?: string;
  uri?: string | null;
}) {
  return (
    <View>
      <PlateImage label={label} height={height} size={size ?? Math.round(height * 0.8)} uri={uri} />
      {badge ? (
        <View style={{ position: "absolute", left: 12, top: 12, paddingHorizontal: 10, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: color.kohl }}>
          <Text style={[textFont("700"), { fontSize: 12, color: color.white }]}>{badge}</Text>
        </View>
      ) : null}
    </View>
  );
}
