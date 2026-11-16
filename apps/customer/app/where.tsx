// "Change city" (round 6, R8): where the food goes, as a full screen (no bottom sheet).
// The saved addresses with a map pin, the phone's location, or a new address; then
// the cities of the visitor's country (Markets), with a search by city or state, and
// every other country behind "Other countries". A live city is for browsing (a point
// inside one of its areas; the bag asks for a real address); a coming-soon city says
// "Coming soon · N people waiting". The choice decides the home's location line and
// so the country: its currency, its kitchens and the languages on the pill.
import {
  Button, color, filterCities, formatNumber, Input, radius, SafeAreaView, space, type, useCountry, useI18n, type MarketCountry,
} from "@bhojango/mobile-core";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { ScreenBar, Section, ui } from "../lib/account-ui";
import { Icon } from "../lib/icons";
import { useWhere, type DropPoint } from "../lib/where";

type City = MarketCountry["regions"][number]["cities"][number];

export default function Where() {
  const { t } = useI18n();
  const { country, countries } = useCountry();
  const { point, market, saved, setPoint, goHere, pickCity } = useWhere();
  const [list, setList] = useState<DropPoint[] | null | "error">(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [othersOpen, setOthersOpen] = useState(false);

  const load = useCallback(() => {
    saved().then(setList).catch(() => setList("error"));
  }, [saved]);
  useFocusEffect(load);

  const shown = useMemo(() => filterCities(countries, q), [countries, q]);
  const home = shown.find((k) => k.code === country?.code) ?? null;
  const others = shown.filter((k) => k.code !== country?.code);
  const othersShown = othersOpen || (!!q.trim() && !home && others.length > 0);

  const done = () => (router.canGoBack() ? router.back() : router.replace("/home"));
  async function go(pick: () => Promise<void>) {
    setBusy(true);
    setProblem(null);
    try {
      await pick();
      done();
    } catch {
      setProblem(t("app.home.locate_failed"));
    } finally {
      setBusy(false);
    }
  }

  const cityRows = (k: MarketCountry) =>
    k.regions.map((r) => (
      <View key={r.code} style={{ gap: space[1] }}>
        <Text style={[type.small, { color: color.muted }]}>{r.name}</Text>
        {r.cities.map((c) => (
          <CityRow key={c.code} c={c} on={point?.browse === true && market?.city_code === c.code} disabled={busy}
            onPick={() => void go(() => pickCity(c, k.code))} locale={k.locales?.[0]} />
        ))}
      </View>
    ));

  return (
    <SafeAreaView testID="where-screen" style={ui.screen} edges={["top", "left", "right", "bottom"]}>
      <ScreenBar title={t("cities.choose_title")} fallback="/home" testID="where-title" />
      <ScrollView contentContainerStyle={ui.scroll} keyboardShouldPersistTaps="handled">
        <Text style={ui.muted}>{t("cities.choose_note")}</Text>
        <Section title={t("account.addresses.title")} testID="where-saved">
          {list === null ? <ActivityIndicator color={color.peacock} /> : null}
          {list === "error" ? <Text style={ui.muted}>{t("account.addresses.unavailable")}</Text> : null}
          {Array.isArray(list) && !list.length ? <Text style={ui.muted}>{t("account.addresses.empty")}</Text> : null}
          {Array.isArray(list) ? list.map((p, i) => {
            const on = !!point?.addressId && point.addressId === p.addressId;
            return (
              <Pressable key={p.addressId ?? i} testID={`where-address-${i}`} accessibilityRole="button" accessibilityState={{ selected: on }}
                disabled={busy} onPress={() => void go(() => setPoint(p))}
                style={({ pressed }) => [styles.row, i === list.length - 1 && { borderBottomWidth: 0 }, pressed && { opacity: 0.85 }]}>
                <Icon name="pin" size={20} stroke={color.peacock} />
                <View style={{ flex: 1 }}>
                  <Text style={[type.label, { color: color.kohl }]}>{p.label || t("app.home.current_location")}</Text>
                  {p.city ? <Text style={[type.small, { color: color.muted }]}>{[p.city, p.country].filter(Boolean).join(", ")}</Text> : null}
                </View>
                {on ? <Icon name="check" size={18} stroke={color.peacock} /> : null}
              </Pressable>
            );
          }) : null}
        </Section>
        {problem ? <Text accessibilityRole="alert" style={[type.small, { color: color.chili }]}>{problem}</Text> : null}
        <View style={{ gap: space[3] }}>
          <Button testID="where-here" title={t("app.home.use_location")} variant="secondary" block loading={busy} onPress={() => void go(goHere)} />
          <Button testID="where-add" title={t("account.addresses.add")} variant="secondary" block onPress={() => router.push("/account/address")} />
        </View>

        <Section title={home?.name ?? country?.name ?? t("cities.title")} testID="where-cities">
          <Input testID="where-city-search" shape="pill" value={q} onChangeText={setQ} placeholder={t("cities.search")}
            accessibilityLabel={t("cities.search")} autoCorrect={false} />
          {home ? cityRows(home) : (
            <Text style={ui.muted}>{q.trim() && country ? t("cities.no_match_in", { country: country.name }) : t("cities.no_match")}</Text>
          )}
        </Section>
        {others.length > 0 ? (
          <View style={{ gap: space[3] }}>
            <Pressable testID="where-other-countries" accessibilityRole="button" accessibilityState={{ expanded: othersShown }}
              onPress={() => setOthersOpen((o) => !o)} style={styles.disclosure}>
              <Text style={[type.label, { color: color.peacock, flex: 1 }]}>{t("cities.other_countries")}</Text>
              <View style={othersShown ? { transform: [{ rotate: "180deg" }] } : null}><Icon name="chevron" size={18} stroke={color.peacock} /></View>
            </Pressable>
            {othersShown ? others.map((k) => (
              <Section key={k.code} title={k.name}>{cityRows(k)}</Section>
            )) : null}
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

/** A city: live ones pick it (browse there); coming-soon ones say how many are waiting. */
function CityRow({ c, on, disabled, onPick, locale }: { c: City; on: boolean; disabled: boolean; onPick: () => void; locale?: string }) {
  const { t } = useI18n();
  const live = c.status === "live";
  const waiting = Number(c.waiting ?? 0);
  const status = live
    ? t("cities.kitchens", { count: c.restaurants })
    : [t("common.coming_soon"), waiting > 0 ? t("common.people_waiting", { count: waiting, n: formatNumber(waiting, locale) }) : null].filter(Boolean).join(" · ");
  const body = (
    <>
      <View style={{ flex: 1 }}>
        <Text style={[type.label, { color: live ? color.kohl : color.muted }]}>{c.name}</Text>
        <Text style={[type.small, { color: live ? color.peacock : color.muted }]}>{status}</Text>
      </View>
      {on ? <Icon name="check" size={18} stroke={color.peacock} /> : null}
    </>
  );
  return live ? (
    <Pressable testID={`where-city-${c.code}`} accessibilityRole="button" accessibilityState={{ selected: on }} disabled={disabled}
      onPress={onPick} style={({ pressed }) => [styles.city, pressed && { opacity: 0.85 }]}>
      {body}
    </Pressable>
  ) : (
    <View testID={`where-city-${c.code}`} style={styles.city}>{body}</View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 10, minHeight: 56, borderBottomWidth: 1, borderBottomColor: color.divider },
  city: { flexDirection: "row", alignItems: "center", gap: 10, minHeight: 52, paddingVertical: space[2] },
  disclosure: {
    flexDirection: "row", alignItems: "center", minHeight: 48, paddingHorizontal: space[4], borderRadius: radius.card,
    backgroundColor: color.white,
  },
});
