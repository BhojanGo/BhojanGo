// The partner tablet's pieces, as drawn on PartnerOrders.html / PartnerMenu.html
// (1194 × 834 landscape): the dark side rail, pills, cards, segmented choices.
import { color, displayFont, radius, textFont } from "@bhojango/mobile-core";
import type { ReactNode } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type StyleProp, type TextStyle, type ViewStyle } from "react-native";
import Svg, { Circle, Path } from "react-native-svg";

export const tone = {
  ...color,
  rail: "#111418",
  railOn: "#1B2C2F",
  railText: "#A9B8BA",
  kesarSoft: "#F7EBD3", // preparing badge, notes
  kesarInk: "#5C4100",
  reject: "#8C1D18",
};

export { color, displayFont, radius, textFont };

const PATHS = {
  orders: "M6 3h12l1 18H5zM9 7a3 3 0 0 0 6 0",
  menu: "M4 6h16M4 12h16M4 18h10",
  payouts: "M3 10h18L12 4zM5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18",
  help: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17h.01",
  back: "M15 5l-7 7 7 7",
  chevron: "m9 6 6 6-6 6",
  check: "m5 12 5 5 9-10",
  search: "M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zM20 20l-4.3-4.3",
  close: "M6 6l12 12M18 6 6 18",
  doc: "M7 3h7l5 5v13H7zM14 3v5h5",
  bell: "M6 16V11a6 6 0 1 1 12 0v5l2 2H4zM10 21h4",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 11v6M12 7.5h.01",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 22, stroke = color.kohl, width = 2 }: { name: IconName; size?: number; stroke?: string; width?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round">
      <Path d={PATHS[name]} />
    </Svg>
  );
}

export function Mark({ size = 40 }: { size?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 40 40" accessibilityLabel="BhojanGo">
      <Circle cx={20} cy={20} r={20} fill={color.peacock} />
      <Path d="M14 9.5v17" stroke="#fff" strokeWidth={3.6} strokeLinecap="round" fill="none" />
      <Circle cx={20.5} cy={23} r={6} fill="none" stroke="#fff" strokeWidth={3.6} />
      <Path d="M19 14c-1.1-1.3 1.1-2.4 0-4M23.5 14c-1.1-1.3 1.1-2.4 0-4" stroke={color.kesarBright} strokeWidth={1.8} strokeLinecap="round" fill="none" />
    </Svg>
  );
}

type Kind = "primary" | "dark" | "outline" | "danger";

export function Btn({ title, onPress, kind = "outline", height = 48, disabled, busy, style, grow, testID, label }: {
  title: string; onPress?: () => void; kind?: Kind; height?: number; disabled?: boolean; busy?: boolean;
  style?: StyleProp<ViewStyle>; grow?: boolean; testID?: string; label?: string;
}) {
  const k = BTN[kind];
  return (
    <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: disabled || busy, busy }}
      disabled={disabled || busy} onPress={onPress}
      style={({ pressed }) => [s.btn, { height, backgroundColor: k.bg, borderColor: k.border ?? k.bg, borderWidth: k.border ? 1.5 : 0,
        opacity: disabled ? 0.45 : pressed ? 0.85 : 1 }, grow && { flexGrow: 1 }, style]}>
      {busy ? <ActivityIndicator color={k.fg} /> : null}
      <Text style={[textFont(kind === "outline" ? "700" : "800"), { color: k.fg, fontSize: height >= 56 ? 17 : 14 }]}>{title}</Text>
    </Pressable>
  );
}

const BTN: Record<Kind, { bg: string; fg: string; border?: string }> = {
  primary: { bg: color.peacock, fg: color.white },
  dark: { bg: color.kohl, fg: color.white },
  outline: { bg: color.white, fg: color.kohl, border: color.lineStrong },
  danger: { bg: color.white, fg: tone.reject, border: color.lineStrong },
};

export function Segmented<T extends string | number>({ options, value, onChange, label, height = 44 }: {
  options: { value: T; label: string }[]; value: T; onChange: (v: T) => void; label: string; height?: number;
}) {
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={label} style={s.seg}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <Pressable key={String(o.value)} accessibilityRole="radio" accessibilityState={{ checked: on }} accessibilityLabel={`${label} ${o.label}`}
            onPress={() => onChange(o.value)} style={[s.segBtn, { height }, on && s.segOn]}>
            <Text style={[textFont(on ? "800" : "600"), { fontSize: 15, color: on ? color.kohl : color.muted }]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Count({ n, bg, fg }: { n: number; bg: string; fg: string }) {
  return (
    <View style={[s.count, { backgroundColor: bg }]}><Text style={[textFont("800"), { fontSize: 12, color: fg }]}>{n}</Text></View>
  );
}

export function Card({ children, style, highlight }: { children: ReactNode; style?: StyleProp<ViewStyle>; highlight?: boolean }) {
  return <View style={[s.card, highlight && s.cardHi, style]}>{children}</View>;
}

export const t = StyleSheet.create({
  h1: { ...displayFont("600"), fontSize: 24, letterSpacing: -0.4, color: color.kohl },
  big: { ...displayFont("600"), fontSize: 34, letterSpacing: -0.8, color: color.kohl },
  title: { ...textFont("800"), fontSize: 17, color: color.kohl },
  body: { ...textFont("400"), fontSize: 15, color: color.kohl },
  muted: { ...textFont("400"), fontSize: 13, color: color.muted },
  label: { ...textFont("700"), fontSize: 13, color: color.kohl },
}) as Record<"h1" | "big" | "title" | "body" | "muted" | "label", TextStyle>;

const s = StyleSheet.create({
  btn: { borderRadius: radius.pill, paddingHorizontal: 20, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 8 },
  seg: { flexDirection: "row", padding: 4, borderRadius: radius.pill, backgroundColor: color.porcelain },
  segBtn: { flex: 1, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  segOn: { backgroundColor: color.white, shadowColor: "#111418", shadowOpacity: 0.12, shadowRadius: 3, shadowOffset: { width: 0, height: 1 }, elevation: 2 },
  count: { minWidth: 24, height: 24, paddingHorizontal: 8, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  card: { backgroundColor: color.white, borderRadius: radius.card, borderWidth: 1, borderColor: color.line, padding: 20, gap: 12 },
  cardHi: {
    borderWidth: 2, borderColor: color.peacock, gap: 16,
    shadowColor: color.peacock, shadowOpacity: 0.14, shadowRadius: 24, shadowOffset: { width: 0, height: 8 }, elevation: 6,
  },
}) as Record<string, ViewStyle>;
