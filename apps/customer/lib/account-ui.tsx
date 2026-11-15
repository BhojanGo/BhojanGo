// Building blocks the account screens share: the top bar with a back button,
// section cards, labelled rows, menu rows, stars and a status line.
import { color, radius, space, textFont, useI18n } from "@bhojango/mobile-core";
import { router, type Href } from "expo-router";
import type { ReactNode } from "react";
import { Pressable, StyleSheet, Text, View, type StyleProp, type TextStyle, type ViewStyle } from "react-native";

import { Icon, type IconName } from "./icons";

/** Back (to `fallback` when the screen was opened by a link) and the screen's title. */
export function ScreenBar({ title, fallback = "/account", testID }: { title: string; fallback?: Href; testID?: string }) {
  const { t } = useI18n();
  return (
    <View style={ui.bar}>
      <Pressable testID="back" accessibilityRole="button" accessibilityLabel={t("common.back")} hitSlop={6}
        onPress={() => (router.canGoBack() ? router.back() : router.replace(fallback))} style={ui.back}>
        <Icon name="back" />
      </Pressable>
      <Text testID={testID} accessibilityRole="header" numberOfLines={1} style={[textFont("800"), { flex: 1, fontSize: 18, color: color.kohl }]}>{title}</Text>
    </View>
  );
}

export function Section({ title, note, children, style, testID }: {
  title?: string; note?: string; children: ReactNode; style?: StyleProp<ViewStyle>; testID?: string;
}) {
  return (
    <View testID={testID} style={[ui.card, style]}>
      {title ? <Text accessibilityRole="header" style={ui.h2}>{title}</Text> : null}
      {note ? <Text style={ui.muted}>{note}</Text> : null}
      {children}
    </View>
  );
}

/** label | value (+ note) | action. */
export function Row({ label, value, note, action, last }: { label: string; value: ReactNode; note?: ReactNode; action?: ReactNode; last?: boolean }) {
  return (
    <View style={[ui.row, last && { borderBottomWidth: 0 }]}>
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={[textFont("700"), { fontSize: 13, color: color.muted }]}>{label}</Text>
        <Text style={[textFont("700"), { fontSize: 16, color: color.kohl }]}>{value}</Text>
        {note ? <Text style={ui.small}>{note}</Text> : null}
      </View>
      {action}
    </View>
  );
}

/** A row in the account menu: icon, label, a short value, then a chevron. */
export function MenuRow({ label, value, icon, href, testID, last }: {
  label: string; value?: string; icon: IconName; href: Href; testID: string; last?: boolean;
}) {
  return (
    <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={value ? `${label}, ${value}` : label} onPress={() => router.push(href)}
      style={({ pressed }) => [ui.menu, last && { borderBottomWidth: 0 }, pressed && { opacity: 0.7 }]}>
      <View style={ui.menuIcon}><Icon name={icon} size={20} stroke={color.peacockDeep} /></View>
      <View style={{ flex: 1 }}>
        <Text style={[textFont("700"), { fontSize: 16, color: color.kohl }]}>{label}</Text>
        {value ? <Text numberOfLines={1} style={ui.small}>{value}</Text> : null}
      </View>
      <Icon name="arrow" size={18} stroke={color.muted} />
    </Pressable>
  );
}

/** A text button in Peacock (edit, remove, make default). */
export function LinkButton({ title, onPress, danger, testID, disabled }: { title: string; onPress: () => void; danger?: boolean; testID?: string; disabled?: boolean }) {
  return (
    <Pressable testID={testID} accessibilityRole="button" hitSlop={8} onPress={onPress} disabled={disabled} style={{ opacity: disabled ? 0.5 : 1, minHeight: 32, justifyContent: "center" }}>
      <Text style={[textFont("800"), { fontSize: 14, color: danger ? color.chili : color.peacock }]}>{title}</Text>
    </Pressable>
  );
}

/** Five stars, `value` of them filled. */
export function Stars({ value, size = 22 }: { value: number; size?: number }) {
  return (
    <View style={{ flexDirection: "row", gap: 2 }} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      {[1, 2, 3, 4, 5].map((n) => (
        <Icon key={n} name="star" size={size} stroke={n <= value ? color.kesar : color.lineStrong} fill={n <= value ? color.kesar : "none"} />
      ))}
    </View>
  );
}

/** Loading, an error with a retry, or nothing. */
export function Status({ loading, error, onRetry }: { loading?: boolean; error?: string | null; onRetry?: () => void }) {
  const { t } = useI18n();
  if (loading) return <Text accessibilityRole="progressbar" style={ui.muted}>{t("account.loading")}</Text>;
  if (!error) return null;
  return (
    <View style={{ gap: 6 }}>
      <Text accessibilityRole="alert" style={ui.muted}>{error}</Text>
      {onRetry ? <LinkButton title={t("common.retry")} onPress={onRetry} /> : null}
    </View>
  );
}

type ViewKey = "screen" | "scroll" | "bar" | "back" | "card" | "row" | "menu" | "menuIcon";
type TextKey = "h2" | "muted" | "small" | "error" | "ok" | "eyebrow";

/** The account screens' shared styles. */
export const ui: Record<ViewKey, ViewStyle> & Record<TextKey, TextStyle> = StyleSheet.create({
  screen: { flex: 1, backgroundColor: color.porcelain },
  scroll: { padding: space[5], gap: space[4], paddingBottom: space[8] * 2 },
  bar: { flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: space[5], paddingVertical: space[3] },
  back: { width: 44, height: 44, borderRadius: radius.pill, backgroundColor: color.white, alignItems: "center", justifyContent: "center" },
  card: { backgroundColor: color.white, borderRadius: radius.card, padding: space[4], gap: space[3] },
  h2: { ...textFont("800"), fontSize: 17, color: color.kohl },
  muted: { ...textFont("400"), fontSize: 14, lineHeight: 20, color: color.muted },
  small: { ...textFont("400"), fontSize: 13, lineHeight: 18, color: color.muted },
  error: { ...textFont("600"), fontSize: 14, color: color.chili },
  ok: { ...textFont("700"), fontSize: 14, color: color.peacockDeep },
  row: { flexDirection: "row", alignItems: "center", gap: space[3], paddingVertical: space[3], borderBottomWidth: 1, borderBottomColor: color.line },
  menu: { flexDirection: "row", alignItems: "center", gap: space[3], minHeight: 60, paddingVertical: space[2], borderBottomWidth: 1, borderBottomColor: color.line },
  menuIcon: { width: 40, height: 40, borderRadius: radius.pill, backgroundColor: color.peacockTint, alignItems: "center", justifyContent: "center" },
  eyebrow: { ...textFont("800"), fontSize: 12, letterSpacing: 1, textTransform: "uppercase", color: color.muted },
});
