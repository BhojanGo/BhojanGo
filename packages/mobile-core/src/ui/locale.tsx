// Language, country and test-site building blocks for the three apps (round 4).
import { useRef, useState, type ReactNode } from "react";
import { Dimensions, type HostInstance, Modal, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import { SafeAreaInsetsContext, useSafeAreaInsets } from "react-native-safe-area-context";
import Svg, { Circle, Path } from "react-native-svg";

import { appEnv, isTestEnvironment, type AppEnv } from "../env";
import { LANGUAGES, useCountry, useI18n, type Language } from "../i18n";
import type { MarketCountry } from "../locale";
import { color, dark, elevation, radius, space } from "./theme";
import { type } from "./type";

/** "light" on the customer and partner apps' porcelain screens, "dark" on the rider app. */
export type Tone = "light" | "dark";

function tones(tone: Tone) {
  return tone === "dark"
    ? { fg: dark.text, muted: dark.muted, line: dark.line, on: dark.raised, accent: color.kesarBright }
    : { fg: color.kohl, muted: color.muted, line: color.line, on: color.peacockTint, accent: color.peacock };
}

function Choice({ label, sub, on, onPress, tone, testID }: {
  label: string; sub?: string; on: boolean; onPress: () => void; tone: Tone; testID?: string;
}) {
  const c = tones(tone);
  return (
    <Pressable testID={testID} accessibilityRole="radio" accessibilityState={{ checked: on }} onPress={onPress}
      style={({ pressed }) => [styles.row, { borderColor: on ? c.accent : c.line }, on && { backgroundColor: c.on }, pressed && { opacity: 0.85 }]}>
      <View style={{ flex: 1 }}>
        <Text style={[type.label, { color: c.fg }]}>{label}</Text>
        {sub ? <Text style={[type.small, { color: c.muted }]}>{sub}</Text> : null}
      </View>
      <View style={[styles.radio, { borderColor: on ? c.accent : c.muted }]}>
        {on ? <View style={[styles.dot, { backgroundColor: c.accent }]} /> : null}
      </View>
    </Pressable>
  );
}

/**
 * The languages the current country offers (its Markets locales, the same list as
 * the website's), each in its own script. Choosing one switches the
 * app at once and is kept on the device. Prices and dates keep the country's format.
 * Put it in an account/settings screen or inside a <Sheet title={t("header.language")}>.
 */
export function LanguagePicker({ tone = "light", onChange, style, addressNote = false }: {
  tone?: Tone;
  /** Called after the switch (e.g. close the sheet). */
  onChange?: (language: Language) => void;
  style?: StyleProp<ViewStyle>;
  /** Customer app only: "Country is separate: prices and kitchens follow your address." Partners have no address. */
  addressNote?: boolean;
}) {
  const { t, language, languages, setLanguage } = useI18n();
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={t("header.language")} style={[{ gap: space[2] }, style]}>
      {languages.map((lang) => (
        <Choice key={lang} testID={`language-${lang}`} label={LANGUAGES[lang].name} on={lang === language} tone={tone}
          onPress={() => void setLanguage(lang).then(() => onChange?.(lang))} />
      ))}
      {addressNote ? <Text testID="language-address-note" style={[type.small, { color: tones(tone).muted }]}>{t("header.language_note")}</Text> : null}
    </View>
  );
}

function Globe({ size = 16, stroke }: { size?: number; stroke: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <Circle cx={12} cy={12} r={9} />
      <Path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z" />
    </Svg>
  );
}

/**
 * The header's language pill (round 6, like the website's): a small globe and the
 * language's code ("EN", "HI", "TE", "ES"). A tap opens a plain list under the pill
 * (not a sheet): the current country's languages (Markets locales), each named in
 * its own script, no flags. Choosing one switches the app at once and is kept on
 * this device only (nothing is saved on the account). testIDs (the website's):
 * "language-pill" (read aloud "Language: English"), "language-pill-code" ("EN"),
 * "language-menu", "language-option-<code>" ("language-option-te").
 */
export function LanguagePill({ tone = "light", style }: { tone?: Tone; style?: StyleProp<ViewStyle> }) {
  const { t, language, options, setLanguage } = useI18n();
  const ref = useRef<HostInstance>(null);
  const [at, setAt] = useState<{ top: number; left?: number; right?: number } | null>(null);
  const name = LANGUAGES[language].name;
  const c = tones(tone);
  const surface = tone === "dark" ? dark.raised : color.white;

  const open = () => {
    const win = Dimensions.get("window");
    const place = (x: number, y: number, w: number, h: number) =>
      setAt(x + w / 2 > win.width / 2 ? { top: y + h + 6, right: Math.max(space[3], win.width - x - w) } : { top: y + h + 6, left: Math.max(space[3], x) });
    if (ref.current) ref.current.measureInWindow(place);
    else setAt({ top: 96, right: space[4] });
  };
  const choose = (lang: Language) => {
    setAt(null);
    if (lang !== language) void setLanguage(lang);
  };

  return (
    <>
      <Pressable ref={ref} testID="language-pill" accessibilityRole="button"
        accessibilityLabel={t("header.language_pill", { language: name })} accessibilityState={{ expanded: at != null }}
        hitSlop={6} onPress={open}
        style={({ pressed }) => [styles.pill, { borderColor: tone === "dark" ? dark.lineStrong : color.line, backgroundColor: surface },
          pressed && { opacity: 0.85 }, style]}>
        <Globe stroke={c.fg} />
        <Text testID="language-pill-code" style={[type.label, { color: c.fg }]}>{language.toUpperCase()}</Text>
      </Pressable>
      <Modal visible={at != null} transparent animationType="fade" statusBarTranslucent navigationBarTranslucent
        onRequestClose={() => setAt(null)}>
        <Pressable testID="language-menu-backdrop" accessibilityLabel={t("common.close")} style={StyleSheet.absoluteFill} onPress={() => setAt(null)} />
        {at ? (
          <View testID="language-menu" accessibilityRole="menu" accessibilityLabel={t("header.language")}
            style={[styles.menu, at, { backgroundColor: surface, borderColor: tone === "dark" ? dark.lineStrong : color.line }]}>
            {options.map((o) => {
              const on = o.code === language;
              return (
                <Pressable key={o.code} testID={`language-option-${o.code}`} accessibilityRole="menuitem" accessibilityLabel={o.name}
                  accessibilityState={{ selected: on }} onPress={() => choose(o.code)}
                  style={({ pressed }) => [styles.option, (on || pressed) && { backgroundColor: c.on }]}>
                  <Text style={[on ? type.label : type.body, { color: c.fg, flex: 1 }]}>{o.name}</Text>
                  {on ? <Check stroke={c.accent} /> : null}
                </Pressable>
              );
            })}
          </View>
        ) : null}
      </Modal>
    </>
  );
}

function Check({ stroke }: { stroke: string }) {
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
      <Path d="M5 12.5l4.5 4.5L19 7.5" />
    </Svg>
  );
}

/**
 * The country-code box before a phone number: shows the country's code and
 * phone_code (Markets) and steps to the next Markets country on a tap. Pair it with
 * e164(country.phone_code, typed) and send country.code to the API. testID:
 * "phone-country-<code>" (Maestro steps until "phone-country-IN" is visible).
 */
export function PhoneCountryButton({ value, onChange, tone = "light", style }: {
  value: MarketCountry | null;
  onChange: (country: MarketCountry) => void;
  tone?: Tone;
  style?: StyleProp<ViewStyle>;
}) {
  const { t } = useI18n();
  const { countries } = useCountry();
  const c = tones(tone);
  const next = () => {
    if (!countries.length) return;
    const i = value ? countries.findIndex((x) => x.code === value.code) : -1;
    onChange(countries[(i + 1) % countries.length]!);
  };
  return (
    <Pressable accessibilityRole="button" testID={`phone-country-${value?.code ?? "none"}`}
      accessibilityLabel={value ? t("app.phone.country_code", { country: value.name, code: value.phone_code }) : t("app.phone.choose_country")}
      onPress={next} style={[styles.cc, { borderColor: tone === "dark" ? dark.lineStrong : color.lineStrong }, style]}>
      <Text style={[type.label, { color: c.fg }]}>{value ? `${value.code} ${value.phone_code}` : "…"}</Text>
    </Pressable>
  );
}

/** "Test site: demo kitchens, no real orders or payments" (app.test_banner). */
export function TestBanner({ tone = "light" }: { tone?: Tone }) {
  const { t } = useI18n();
  return (
    <View accessibilityRole="summary" testID="test-banner" style={[styles.banner, tone === "dark" ? styles.bannerDark : styles.bannerLight]}>
      <Text numberOfLines={3} maxFontSizeMultiplier={1.5} style={[type.caption, styles.bannerText, { color: tone === "dark" ? color.kesarBright : color.kohl }]}>
        {t("app.test_banner")}
      </Text>
    </View>
  );
}

/**
 * Wrap the root Stack: in every environment but production (EXPO_PUBLIC_APP_ENV) a
 * thin banner sits under the status bar, and the screens below it see no top inset
 * through useSafeAreaInsets() and mobile-core's SafeAreaView (not the native
 * SafeAreaView of react-native-safe-area-context: it measures the window itself,
 * ignores this context and padded the status bar twice; ui/safe-area.tsx). Tab bars and the bottom
 * inset are untouched. In production it renders the children only.
 */
export function WithTestBanner({ children, tone = "light", env = appEnv() }: { children: ReactNode; tone?: Tone; env?: AppEnv }) {
  const insets = useSafeAreaInsets();
  if (!isTestEnvironment(env)) return <>{children}</>;
  return (
    <View style={{ flex: 1 }}>
      <View style={[{ paddingTop: insets.top }, tone === "dark" ? styles.bannerDark : styles.bannerLight]}>
        <TestBanner tone={tone} />
      </View>
      <SafeAreaInsetsContext.Provider value={{ ...insets, top: 0 }}>
        <View style={{ flex: 1 }}>{children}</View>
      </SafeAreaInsetsContext.Provider>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    minHeight: 56, flexDirection: "row", alignItems: "center", gap: space[3], paddingHorizontal: space[4],
    borderRadius: radius.card, borderWidth: 1.5,
  },
  radio: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, alignItems: "center", justifyContent: "center" },
  dot: { width: 10, height: 10, borderRadius: 5 },
  pill: {
    height: 40, flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: space[3], borderRadius: radius.pill, borderWidth: 1,
  },
  menu: {
    position: "absolute", minWidth: 200, maxWidth: 280, paddingVertical: space[2], borderRadius: radius.card, borderWidth: 1, ...elevation.float,
  },
  option: { minHeight: 48, flexDirection: "row", alignItems: "center", gap: space[3], paddingHorizontal: space[4] },
  cc: { height: 56, paddingHorizontal: space[4], borderRadius: radius.card, borderWidth: 1.5, justifyContent: "center" },
  banner: { paddingHorizontal: space[4], paddingVertical: 6, alignItems: "center" },
  bannerLight: { backgroundColor: color.kesarBright },
  bannerDark: { backgroundColor: dark.raised },
  bannerText: { textAlign: "center", alignSelf: "stretch" }, // at 200 % font the centred line overflowed both edges (R9)
});
