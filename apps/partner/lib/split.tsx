// Landscape sign-in frame: a Peacock panel on the left, the form on the right.
import type { ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { color, displayFont, Mark, textFont } from "./ui";

export function Split({ children }: { children: ReactNode }) {
  return (
    <SafeAreaView style={s.screen} edges={["left", "right"]}>
      <View style={s.brand}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
          <Mark size={44} />
          <Text style={[textFont("800"), { color: color.white, fontSize: 18 }]}>BhojanGo Partner</Text>
        </View>
        <Text style={[displayFont("600"), s.hero]}>Your kitchen,{"\n"}your prices,{"\n"}paid every week.</Text>
        <Text style={[textFont("400"), { color: "#CFE3E5", fontSize: 16, lineHeight: 24 }]}>
          New orders ring on this tablet. Accept, cook, hand over — the rider and the customer see every step.
        </Text>
      </View>
      <View style={s.form}>{children}</View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, flexDirection: "row", backgroundColor: color.white },
  brand: { width: "42%", backgroundColor: color.peacock, padding: 48, gap: 32, justifyContent: "center" },
  hero: { color: color.white, fontSize: 44, lineHeight: 48, letterSpacing: -1.2 },
  form: { flex: 1, paddingHorizontal: 72, justifyContent: "center", gap: 16 },
});
