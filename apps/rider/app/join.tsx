// Sign up to deliver: your name, date of birth, vehicle and city, then the
// onboarding checklist (licence, insurance, payout account, background check).
// The minimum age and the vehicles are the city's country's rules (Markets, via
// GET /delivery/sign-up): this screen checks them to help, POST /riders/apply
// enforces them. A number that already orders food on BhojanGo can't also deliver.
import { api, ApiError, field, LoadError, SafeAreaView, type, unwrap, useFirstLoad, useI18n, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { RiderMark } from "../lib/icons";
import { ageOn, dateOrder, type DatePart } from "../lib/signup";
import { night, radius, space, ui } from "../lib/theme";

type City = { code: string; name: string; region: string; country: string };
type Rules = { min_age: number; vehicles: string[]; today: string };

export default function Join() {
  const adopt = useSession((s) => s.adopt);
  const signOut = useSession((s) => s.signOut);
  const { t, language, formatLocale } = useI18n();
  // Markets' cities (R9: a spinner while they load, the error and Retry if they can't).
  const cityList = useFirstLoad(async () => unwrap(await api.core.GET("/api/v1/markets/cities")) as City[], []);
  const cities = cityList.data ?? [];
  const [picked, setCity] = useState<string | null>(null);
  const city = picked ?? cities[0]?.code ?? null;
  const [rules, setRules] = useState<Record<string, Rules | "error">>({});
  const [name, setName] = useState("");
  const [dob, setDob] = useState<Record<DatePart, string>>({ day: "", month: "", year: "" });
  const [vehicle, setVehicle] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);


  const country = cities.find((c) => c.code === city)?.country ?? null;
  const got = country ? rules[country] : undefined;
  const r = got && got !== "error" ? got : null;

  useEffect(() => {
    if (!country || rules[country]) return;
    api.core.GET("/api/v1/delivery/sign-up", { params: { query: { country } } })
      .then((res) => {
        const x = unwrap(res) as Rules;
        setRules((m) => ({ ...m, [country]: x }));
      })
      .catch(() => setRules((m) => ({ ...m, [country]: "error" })));
  }, [country, rules]);

  // A vehicle another country allows isn't offered here; a single choice is made for you.
  const chosen = !r ? null : vehicle && r.vehicles.includes(vehicle) ? vehicle : r.vehicles.length === 1 ? r.vehicles[0]! : null;

  const iso = dob.year.length === 4 && dob.month && dob.day
    ? `${dob.year}-${dob.month.padStart(2, "0")}-${dob.day.padStart(2, "0")}` : "";
  const age = r && iso ? ageOn(iso, r.today) : null;
  const dobProblem = !r || !iso ? null
    : age === null ? t("rider.join.dob_invalid")
      : age < r.min_age ? t("rider.join.dob_under", { age: r.min_age }) : null;

  async function apply() {
    if (!city || !chosen) return;
    setBusy(true);
    setError(null);
    try {
      const tokens = unwrap(await api.core.POST("/api/v1/riders/apply", {
        body: { full_name: name.trim(), city_code: city, date_of_birth: iso, vehicle: chosen, language },
      }));
      await adopt(tokens as { access_token: string; refresh_token: string });
      router.replace("/drive");
    } catch (e) {
      // The API's refusals (too young, a vehicle the country doesn't allow) come in the app's language.
      setError(e instanceof ApiError ? e.message : t("rider.join.failed"));
    } finally {
      setBusy(false);
    }
  }

  const ok = name.trim().split(/\s+/).length >= 2 && !!city && !!r && age !== null && age >= r.min_age
    && !!chosen && !busy;
  const order = dateOrder(formatLocale);
  const parts: Record<DatePart, { label: string; max: number; flex: number }> = {
    day: { label: t("rider.join.dob_day"), max: 2, flex: 1 },
    month: { label: t("rider.join.dob_month"), max: 2, flex: 1 },
    year: { label: t("rider.join.dob_year"), max: 4, flex: 1.5 },
  };
  return (
    <SafeAreaView testID="join-screen" style={ui.screen}>
      <ScrollView contentContainerStyle={{ padding: space[5], gap: space[4] }} keyboardShouldPersistTaps="handled">
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}><RiderMark /><Text style={ui.bold}>{t("rider.brand")}</Text></View>
        <Text accessibilityRole="header" style={[ui.h1, { marginTop: 24 }]}>{t("rider.join.title")}</Text>
        <Text style={[ui.body, { color: night.muted }]}>{t("rider.join.sub")}</Text>
        <Text style={ui.bold}>{t("rider.join.name")}</Text>
        <TextInput testID="name" accessibilityLabel={t("rider.join.name")} value={name} onChangeText={setName} autoCapitalize="words"
          placeholder={t("rider.join.name_hint")} placeholderTextColor={night.muted} style={[field.bodyLg, s.input]} />

        <Text style={ui.bold}>{t("rider.join.city")}</Text>
        {cityList.status === "error" && !cities.length ? <LoadError error={cityList.error} onRetry={cityList.retry} title={t("rider.join.cities_failed")} tone="dark" /> : null}
        {cityList.status === "loading" && !cities.length ? <ActivityIndicator accessibilityLabel={t("common.loading")} color={night.kesar} /> : null}
        <View style={{ gap: 8 }}>
          {cities.map((c) => (
            <Pressable key={c.code} accessibilityRole="radio" accessibilityState={{ checked: city === c.code }} accessibilityLabel={c.name}
              onPress={() => setCity(c.code)} style={[s.city, city === c.code && { borderColor: night.kesar }]}>
              <Text style={ui.bold}>{c.name}</Text>
              <Text style={ui.muted}>{c.region}</Text>
            </Pressable>
          ))}
        </View>

        {got === "error" ? <Text testID="rules-failed" style={[type.small, { color: night.sosText }]}>{t("rider.join.rules_failed")}</Text> : null}
        {r ? (
          <>
            <Text style={ui.bold}>{t("rider.join.dob")}</Text>
            <View style={{ flexDirection: "row", gap: 8 }}>
              {order.map((k) => (
                <View key={k} style={{ flex: parts[k].flex, gap: 4 }}>
                  <Text style={ui.muted}>{parts[k].label}</Text>
                  <TextInput testID={`dob-${k}`} accessibilityLabel={`${t("rider.join.dob")}: ${parts[k].label}`} value={dob[k]}
                    onChangeText={(v) => setDob((d) => ({ ...d, [k]: v.replace(/\D/g, "").slice(0, parts[k].max) }))}
                    keyboardType="number-pad" maxLength={parts[k].max} autoComplete={k === "year" ? "birthdate-year" : k === "month" ? "birthdate-month" : "birthdate-day"}
                    style={[field.bodyLg, s.input, { textAlign: "center" }, dobProblem ? { borderColor: night.sosText } : null]} />
                </View>
              ))}
            </View>
            {dobProblem ? <Text testID="dob-error" style={[type.small, { color: night.sosText }]}>{dobProblem}</Text> : null}
            <Text style={[type.small, { color: night.muted }]}>{t("rider.join.dob_help", { age: r.min_age })}</Text>

            <Text style={ui.bold}>{t("rider.join.vehicle")}</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
              {r.vehicles.map((v) => {
                const label = t(`deliver_page.vehicle_${v}`);
                const on = chosen === v;
                return (
                  <Pressable key={v} testID={`vehicle-${v}`} accessibilityRole="radio" accessibilityState={{ checked: on }}
                    accessibilityLabel={label} onPress={() => setVehicle(v)} style={[s.chip, on && { borderColor: night.kesar }]}>
                    <Text style={ui.bold}>{label.charAt(0).toLocaleUpperCase() + label.slice(1)}</Text>
                  </Pressable>
                );
              })}
            </View>
          </>
        ) : null}

        {error ? <Text style={[type.small, { color: night.sosText }]}>{error}</Text> : null}
        <Pressable testID="join-continue" accessibilityRole="button" accessibilityState={{ disabled: !ok }} disabled={!ok} onPress={apply}
          style={[ui.cta, { opacity: ok ? 1 : 0.5 }]}>
          <Text style={ui.ctaText}>{busy ? t("rider.join.signing_up") : t("rider.join.continue")}</Text>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={async () => { await signOut(); router.replace("/sign-in"); }}>
          <Text style={[ui.muted, { textAlign: "center" }]}>{t("rider.join.another_number")}</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  input: { height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: night.lineStrong, paddingHorizontal: space[4],
    color: night.text, backgroundColor: night.surface },
  city: { padding: 16, borderRadius: radius.card, borderWidth: 1.5, borderColor: night.lineStrong, backgroundColor: night.surface },
  chip: { minHeight: 48, paddingHorizontal: 18, justifyContent: "center", borderRadius: radius.pill, borderWidth: 1.5,
    borderColor: night.lineStrong, backgroundColor: night.surface },
});
