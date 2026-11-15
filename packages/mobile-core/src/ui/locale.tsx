// Language, country and test-site building blocks for the three apps (round 4).
import type { ReactNode } from "react";
import { Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";
import { SafeAreaInsetsContext, useSafeAreaInsets } from "react-native-safe-area-context";

import { appEnv, isTestEnvironment, type AppEnv } from "../env";
import { LANGUAGES, useCountry, useI18n, type Language } from "../i18n";
import type { MarketCountry } from "../locale";
import { color, dark, radius, space, textFont } from "./theme";

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
        <Text style={[textFont(on ? "800" : "600"), { fontSize: 16, color: c.fg }]}>{label}</Text>
        {sub ? <Text style={[textFont("400"), { fontSize: 13, color: c.muted }]}>{sub}</Text> : null}
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
export function LanguagePicker({ tone = "light", onChange, style }: {
  tone?: Tone;
  /** Called after the switch (e.g. close the sheet). */
  onChange?: (language: Language) => void;
  style?: StyleProp<ViewStyle>;
}) {
  const { t, language, languages, setLanguage } = useI18n();
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={t("header.language")} style={[{ gap: space[2] }, style]}>
      {languages.map((lang) => (
        <Choice key={lang} testID={`language-${lang}`} label={LANGUAGES[lang].name} on={lang === language} tone={tone}
          onPress={() => void setLanguage(lang).then(() => onChange?.(lang))} />
      ))}
      <Text style={[textFont("400"), { fontSize: 13, color: tones(tone).muted }]}>{t("header.language_note")}</Text>
    </View>
  );
}

/** Markets' countries to choose from (when the app can't tell the country). Kept on the device. */
export function CountryPicker({ tone = "light", onChange, style }: {
  tone?: Tone;
  onChange?: (country: MarketCountry) => void;
  style?: StyleProp<ViewStyle>;
}) {
  const { t } = useI18n();
  const { country, countries, chooseCountry } = useCountry();
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={t("header.country_title")} style={[{ gap: space[2] }, style]}>
      {countries.map((c) => (
        <Choice key={c.code} testID={`country-${c.code}`} label={c.name} sub={c.phone_code} on={c.code === country?.code} tone={tone}
          onPress={() => void chooseCountry(c.code).then(() => onChange?.(c))} />
      ))}
    </View>
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
      <Text style={[textFont("800"), { fontSize: 15, color: c.fg }]}>{value ? `${value.code} ${value.phone_code}` : "…"}</Text>
    </Pressable>
  );
}

/** "Test site: demo kitchens, no real orders or payments" (app.test_banner). */
export function TestBanner({ tone = "light" }: { tone?: Tone }) {
  const { t } = useI18n();
  return (
    <View accessibilityRole="summary" testID="test-banner" style={[styles.banner, tone === "dark" ? styles.bannerDark : styles.bannerLight]}>
      <Text numberOfLines={2} style={[textFont("700"), styles.bannerText, { color: tone === "dark" ? color.kesarBright : color.kohl }]}>
        {t("app.test_banner")}
      </Text>
    </View>
  );
}

/**
 * Wrap the root Stack: in every environment but production (EXPO_PUBLIC_APP_ENV) a
 * thin banner sits under the status bar, and the screens below it see no top inset
 * (their SafeAreaView/useSafeAreaInsets don't pad twice). Tab bars and the bottom
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
  cc: { height: 56, paddingHorizontal: space[4], borderRadius: radius.card, borderWidth: 1.5, justifyContent: "center" },
  banner: { paddingHorizontal: space[4], paddingVertical: 6, alignItems: "center" },
  bannerLight: { backgroundColor: color.kesarBright },
  bannerDark: { backgroundColor: dark.raised },
  bannerText: { fontSize: 12, textAlign: "center", letterSpacing: 0.2 },
});
