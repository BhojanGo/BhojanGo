// The design system for the Expo apps (P16): the same components as
// @bhojango/ui on the web, in React Native, from the same tokens.
import { billRows, billTotal, money, type BillLine } from "@bhojango/ui/bill";
import { useEffect, useState, type ReactNode } from "react";
import {
  ActivityIndicator, Animated, Image, Modal, Pressable, StyleSheet, Text, TextInput, View,
  type PressableProps, type StyleProp, type TextInputProps, type TextStyle, type ViewStyle,
} from "react-native";
import Svg, { Circle, Ellipse, Path, Rect } from "react-native-svg";

import { color, dark, elevation, radius, space, textFont, touch, typeStyle } from "./theme";

// ── text ──────────────────────────────────────────────────────────────────────

export function Txt({ variant = "body", style, children, ...rest }: {
  variant?: Parameters<typeof typeStyle>[0];
  style?: StyleProp<TextStyle>;
  children: ReactNode;
  numberOfLines?: number;
  accessibilityRole?: "header" | "text";
}) {
  return (
    <Text style={[{ color: color.kohl }, typeStyle(variant), style]} {...rest}>
      {children}
    </Text>
  );
}

// ── buttons ──────────────────────────────────────────────────────────────────

type ButtonVariant = "primary" | "secondary" | "ghost" | "rider" | "danger";

export function Button({ title, variant = "primary", size = "md", loading, disabled, block, style, ...rest }: PressableProps & {
  title: string;
  variant?: ButtonVariant;
  /** md 48, lg 56 (main action), rider 64 */
  size?: "md" | "lg";
  loading?: boolean;
  block?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const v = BUTTON[variant];
  const height = variant === "rider" ? touch.rider : size === "lg" ? touch.primary : touch.min;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: disabled || loading, busy: loading }}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.button,
        { height, backgroundColor: v.bg, borderColor: v.border ?? v.bg, opacity: disabled ? 0.5 : pressed ? 0.85 : 1 },
        block && { alignSelf: "stretch" },
        style,
      ]}
      {...rest}
    >
      {loading ? <ActivityIndicator color={v.fg} /> : null}
      <Text style={[textFont("800"), { color: v.fg, fontSize: variant === "rider" ? 18 : size === "lg" ? 17 : 15 }]}>{title}</Text>
    </Pressable>
  );
}

const BUTTON: Record<ButtonVariant, { bg: string; fg: string; border?: string }> = {
  primary: { bg: color.peacock, fg: color.white },
  secondary: { bg: color.white, fg: color.kohl, border: color.lineStrong },
  ghost: { bg: "transparent", fg: color.peacock },
  rider: { bg: color.kesarBright, fg: color.kohl },
  danger: { bg: color.chili, fg: color.white },
};

export function Chip({ label, selected, count, onPress }: { label: string; selected?: boolean; count?: number; onPress?: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      hitSlop={4}
      style={[styles.chip, selected ? { backgroundColor: color.peacockTint, borderColor: color.peacock } : null]}
    >
      <Text style={[textFont(selected ? "800" : "600"), { fontSize: 14, color: selected ? color.peacockDeep : color.kohl }]}>{label}</Text>
      {count != null ? (
        <View style={styles.count}>
          <Text style={[textFont("800"), { fontSize: 11, color: color.kohl }]}>{count}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={label} style={styles.segmented}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <Pressable
            key={o.value}
            accessibilityRole="radio"
            accessibilityState={{ checked: on }}
            onPress={() => onChange(o.value)}
            style={[styles.segment, on && { backgroundColor: color.white, ...elevation.float }]}
          >
            <Text style={[textFont(on ? "800" : "600"), { fontSize: 15, color: on ? color.kohl : color.muted }]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

// ── surfaces ─────────────────────────────────────────────────────────────────

export function Card({ tone = "flat", padded = true, style, children }: {
  tone?: "flat" | "outline" | "floating" | "dark";
  padded?: boolean;
  style?: StyleProp<ViewStyle>;
  children: ReactNode;
}) {
  return (
    <View
      style={[
        styles.card,
        padded && { padding: space[4] },
        tone === "outline" && { borderWidth: 1, borderColor: color.line },
        tone === "floating" && elevation.float,
        tone === "dark" && { backgroundColor: dark.surface },
        style,
      ]}
    >
      {children}
    </View>
  );
}

/** The fair bill: every line with who gets the money, then the total. */
export function FairBill({ lines, currency, totalLabel = "You pay" }: { lines: BillLine[]; currency: string; totalLabel?: string }) {
  const rows = billRows(lines, currency);
  return (
    <View accessibilityLabel="The fair bill" style={[styles.card, { padding: space[4] }]}>
      <View style={styles.billHead}>
        <Txt variant="title" style={{ fontSize: 18 }}>The fair bill</Txt>
        <Text style={[textFont("700"), { fontSize: 12, color: color.peacock }]}>who gets each {currency === "INR" ? "rupee" : "dollar"}</Text>
      </View>
      {rows.map((r, i) => (
        <View key={i} style={styles.billRow}>
          <Text style={[textFont(r.accent ? "600" : "400"), styles.billLabel, r.accent && { color: color.peacock }]}>{r.label}</Text>
          <Text style={[textFont("700"), styles.payee]}>{r.payee}</Text>
          <Text style={[textFont(r.accent ? "600" : "400"), styles.billAmount, r.accent && { color: color.peacock }]}>
            {r.struck ? <Text style={{ color: color.faint, textDecorationLine: "line-through" }}>{r.struck} </Text> : null}
            {r.struck ? <Text style={textFont("700")}>{r.amount}</Text> : r.amount}
          </Text>
        </View>
      ))}
      <View style={styles.billTotal}>
        <Text style={[textFont("800"), { fontSize: 18, color: color.kohl }]}>{totalLabel}</Text>
        <Text style={[textFont("800"), { fontSize: 18, color: color.kohl, fontVariant: ["tabular-nums"] }]}>{money(billTotal(lines), currency)}</Text>
      </View>
    </View>
  );
}

export function PlateArt({ size = 96, label }: { size?: number; label?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 120 120" accessibilityLabel={label} accessible={!!label}>
      <Circle cx="60" cy="60" r="56" fill="#FFFFFF" stroke="#D5DEDF" strokeWidth="2" />
      <Circle cx="60" cy="60" r="44" fill="#FBFAF7" />
      <Ellipse cx="64" cy="66" rx="27" ry="21" fill="#E2B866" />
      <Circle cx="56" cy="60" r="3" fill="#8A4B2A" />
      <Circle cx="70" cy="70" r="3" fill="#8A4B2A" />
      <Circle cx="66" cy="58" r="2.5" fill="#4F7F52" />
      <Circle cx="35" cy="38" r="13" fill="#FFFFFF" stroke="#D5DEDF" strokeWidth="2" />
      <Circle cx="35" cy="38" r="9" fill="#F1EFE8" />
    </Svg>
  );
}

/** The plate frame: a dish on a round plate on a soft tinted ground. */
export function PlateImage({ uri, label, height = 118, ground = color.plate, size = 96 }: {
  uri?: string | null;
  label: string;
  height?: number;
  ground?: string;
  size?: number;
}) {
  return (
    <View style={{ height, backgroundColor: ground, alignItems: "center", justifyContent: "center" }}>
      {uri ? (
        <Image source={{ uri }} accessibilityLabel={label} style={{ width: size, height: size, borderRadius: size / 2 }} />
      ) : (
        <PlateArt size={size} label={label} />
      )}
    </View>
  );
}

const STATUS: Record<string, { label: string; bg: string; fg: string; border?: string }> = {
  pending_payment: { label: "Waiting for payment", bg: color.porcelain, fg: color.kohl, border: color.line },
  placed: { label: "Placed", bg: color.porcelain, fg: color.kohl, border: color.line },
  accepted: { label: "Accepted", bg: color.peacockTint, fg: color.peacockDeep },
  preparing: { label: "Cooking", bg: color.peacockTint, fg: color.peacockDeep },
  almost_ready: { label: "Almost ready", bg: color.peacockTint, fg: color.peacockDeep },
  ready: { label: "Ready for pickup", bg: color.peacockTint, fg: color.peacockDeep },
  picked_up: { label: "On the way", bg: color.peacockTint, fg: color.peacockDeep },
  delivered: { label: "Delivered", bg: color.kohl, fg: color.white },
  cancelled: { label: "Cancelled", bg: color.white, fg: color.chili, border: color.chili },
};

export function StatusPill({ status, label }: { status: string; label?: string }) {
  const s = STATUS[status] ?? { label: status, bg: color.porcelain, fg: color.kohl };
  return (
    <View style={[styles.pill, { backgroundColor: s.bg, borderColor: s.border ?? s.bg }]}>
      <Text style={[textFont("700"), { fontSize: 12, color: s.fg }]}>{label ?? s.label}</Text>
    </View>
  );
}

// ── input ────────────────────────────────────────────────────────────────────

export function Input({ label, hint, error, shape = "field", dark: onDark, ...rest }: TextInputProps & {
  label?: string;
  hint?: string;
  error?: string;
  shape?: "field" | "pill";
  dark?: boolean;
}) {
  return (
    <View style={{ gap: space[2] }}>
      {label ? <Text style={[textFont("700"), { fontSize: 14, color: onDark ? dark.text : color.kohl }]}>{label}</Text> : null}
      <TextInput
        accessibilityLabel={label ?? rest.placeholder}
        placeholderTextColor={onDark ? dark.muted : color.muted}
        style={[
          textFont("400"),
          styles.input,
          shape === "pill" ? { borderRadius: radius.pill, height: 54, borderWidth: 0, ...elevation.float } : null,
          error ? { borderColor: color.chili } : null,
          onDark ? { backgroundColor: dark.raised, borderColor: dark.lineStrong, color: dark.text } : null,
        ]}
        {...rest}
      />
      {error || hint ? (
        <Text style={[textFont(error ? "600" : "400"), { fontSize: 13, color: error ? color.chili : onDark ? dark.muted : color.muted }]}>
          {error ?? hint}
        </Text>
      ) : null}
    </View>
  );
}

// ── sheet ────────────────────────────────────────────────────────────────────

/** Bottom sheet (24 px top radius) over a dimmed screen. */
export function Sheet({ visible, onClose, title, children, footer }: {
  visible: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const [slide] = useState(() => new Animated.Value(0));
  useEffect(() => {
    Animated.timing(slide, { toValue: visible ? 1 : 0, duration: 220, useNativeDriver: true }).start();
  }, [visible, slide]);
  return (
    <Modal transparent visible={visible} onRequestClose={onClose} animationType="fade">
      <Pressable style={styles.scrim} onPress={onClose} accessibilityLabel="Close" />
      <Animated.View
        accessibilityViewIsModal
        style={[styles.sheet, { transform: [{ translateY: slide.interpolate({ inputRange: [0, 1], outputRange: [400, 0] }) }] }]}
      >
        <View style={styles.grabber} />
        <Txt variant="h2" accessibilityRole="header">{title}</Txt>
        {children}
        {footer}
      </Animated.View>
    </Modal>
  );
}

// ── tab bar ──────────────────────────────────────────────────────────────────

export interface TabItem {
  key: string;
  label: string;
  icon: (color: string) => ReactNode;
}

/** The floating dark pill: the current tab shows its label on Peacock. */
export function TabBar({ items, current, onSelect }: { items: TabItem[]; current: string; onSelect: (key: string) => void }) {
  return (
    <View accessibilityRole="tablist" style={styles.tabBar}>
      {items.map((t) => {
        const on = t.key === current;
        return (
          <Pressable
            key={t.key}
            accessibilityRole="tab"
            accessibilityLabel={t.label}
            accessibilityState={{ selected: on }}
            onPress={() => onSelect(t.key)}
            style={[styles.tab, on && styles.tabOn]}
          >
            {t.icon(on ? color.white : color.lineStrong)}
            {on ? <Text style={[textFont("700"), { fontSize: 14, color: color.white }]}>{t.label}</Text> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

// ── logo ─────────────────────────────────────────────────────────────────────

export function LogoMark({ size = 40, tone = "teal" }: { size?: number; tone?: "teal" | "white" }) {
  const stroke = tone === "white" ? "#FFFFFF" : color.peacock;
  const steam = tone === "white" ? color.kesarBright : color.kesar;
  return (
    <Svg width={size} height={size} viewBox="0 0 40 40" accessibilityLabel="BhojanGo" accessible>
      <Rect width="40" height="40" fill="transparent" />
      <Path d="M11 5.5v24" stroke={stroke} strokeWidth={5} strokeLinecap="round" fill="none" />
      <Circle cx="20.5" cy="25" r="8.5" fill="none" stroke={stroke} strokeWidth={5} />
      <Path d="M18.5 13.5c-1.6-1.8 1.6-3.4 0-5.6M24.5 13.5c-1.6-1.8 1.6-3.4 0-5.6" stroke={steam} strokeWidth={2.2} strokeLinecap="round" fill="none" />
    </Svg>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: touch.min, borderRadius: radius.pill, borderWidth: 1.5, paddingHorizontal: space[6],
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: space[2],
  },
  chip: {
    height: 40, borderRadius: radius.chip, borderWidth: 1, borderColor: color.line, backgroundColor: color.white,
    paddingHorizontal: space[3], flexDirection: "row", alignItems: "center", gap: space[2],
  },
  count: { minWidth: 20, height: 20, borderRadius: radius.pill, backgroundColor: color.kesar, alignItems: "center", justifyContent: "center", paddingHorizontal: 4 },
  segmented: { flexDirection: "row", padding: 4, borderRadius: radius.pill, backgroundColor: color.porcelain },
  segment: { flex: 1, height: 42, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  card: { backgroundColor: color.white, borderRadius: radius.card, overflow: "hidden" },
  billHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 },
  billRow: { flexDirection: "row", alignItems: "baseline", gap: 10, paddingVertical: 4 },
  billLabel: { flex: 1, fontSize: 14, color: color.kohl },
  payee: { fontSize: 11, color: color.muted },
  billAmount: { fontSize: 14, color: color.kohl, textAlign: "right", fontVariant: ["tabular-nums"] },
  billTotal: {
    marginTop: space[3], paddingTop: space[3], borderTopWidth: 1.5, borderStyle: "dashed", borderTopColor: color.lineStrong,
    flexDirection: "row", justifyContent: "space-between",
  },
  pill: { height: 28, borderRadius: radius.pill, paddingHorizontal: space[3], borderWidth: 1, alignSelf: "flex-start", justifyContent: "center" },
  input: {
    height: touch.primary, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong,
    backgroundColor: color.white, paddingHorizontal: space[4], fontSize: 16, color: color.kohl,
  },
  scrim: { flex: 1, backgroundColor: "rgba(17, 20, 24, 0.4)" },
  sheet: {
    position: "absolute", left: 0, right: 0, bottom: 0, backgroundColor: color.white,
    borderTopLeftRadius: radius.sheet, borderTopRightRadius: radius.sheet, padding: space[6], gap: space[4], ...elevation.sheet,
  },
  grabber: { alignSelf: "center", width: 40, height: 4, borderRadius: 2, backgroundColor: color.lineStrong },
  tabBar: {
    flexDirection: "row", alignItems: "center", gap: 4, height: 64, paddingHorizontal: 8,
    borderRadius: radius.pill, backgroundColor: color.kohl, alignSelf: "center", ...elevation.bar,
  },
  tab: { height: 48, minWidth: 52, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 8 },
  tabOn: { backgroundColor: color.peacock, paddingHorizontal: 18 },
});
