// The prominent disclosure Google Play requires before the background location
// prompt (R19): what is collected, for what, that it happens even when the app is
// closed or not in use, and with whom it is shared. "Allow" opens the system
// prompt (Android: the "Allow all the time" settings page); "No thanks" keeps
// location to while the app is open. Shown only while the delivery partner is
// online: going online (once per app run) or the Drive tab's banner.
// The exact words are in docs/launch/store/play-location-declaration.md.
import { useI18n } from "@bhojango/mobile-core";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { Icon } from "./icons";
import { night, space, ui } from "./theme";

export function BackgroundDisclosure({ visible, onAllow, onNoThanks }: {
  visible: boolean;
  onAllow: () => void;
  onNoThanks: () => void;
}) {
  const { t } = useI18n();
  return (
    <Modal transparent visible={visible} animationType="fade" onRequestClose={onNoThanks}>
      <View style={s.scrim}>
        <View testID="bg-disclosure" accessibilityViewIsModal style={s.card}>
          <ScrollView contentContainerStyle={{ gap: space[4] }}>
            <View style={s.icon}><Icon name="navigate" stroke={night.kesar} size={28} /></View>
            <Text accessibilityRole="header" style={ui.h2}>{t("rider.location.title")}</Text>
            <Text testID="bg-disclosure-body" style={ui.body}>{t("rider.location.body")}</Text>
            <Text style={ui.body}>{t("rider.location.shared")}</Text>
            <Text style={ui.muted}>{t("rider.location.next")}</Text>
          </ScrollView>
          <Pressable testID="bg-allow" accessibilityRole="button" onPress={onAllow} style={ui.cta}>
            <Text style={ui.ctaText}>{t("rider.location.allow")}</Text>
          </Pressable>
          <Pressable testID="bg-no-thanks" accessibilityRole="button" onPress={onNoThanks} style={ui.outline}>
            <Text style={ui.bold}>{t("rider.location.no_thanks")}</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  scrim: { flex: 1, backgroundColor: "rgba(0, 0, 0, 0.6)", justifyContent: "center", padding: space[5] },
  card: { maxHeight: "90%", borderRadius: 28, backgroundColor: night.surface, padding: space[5], gap: space[3] },
  icon: { width: 56, height: 56, borderRadius: 28, backgroundColor: night.raised, alignItems: "center", justifyContent: "center" },
});
