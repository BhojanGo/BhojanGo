// CustomerOutOfArea.html: we don't deliver here yet; leave a number to hear when we do.
import {
  api, Button, color, e164, errorMessage, Input, liveCityNames, SafeAreaView, space, Txt, type, unwrap, useCountry, useI18n,
} from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, Text, View } from "react-native";

import { Icon } from "../lib/icons";
import { outOfAreaPlace } from "../lib/notices";
import { useWhere } from "../lib/where";

export default function OutOfArea() {
  const point = useWhere((s) => s.point);
  const market = useWhere((s) => s.market);
  const { t } = useI18n();
  const { country, countries } = useCountry();
  const cities = liveCityNames(countries); // where we cook now (Markets)
  // The most specific place we know, named only when it is outside every delivery zone
  // (R27: opened by a link, a served neighbourhood was named). Otherwise "your area".
  const place = outOfAreaPlace(point, market);
  const [phone, setPhone] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function join() {
    if (!point) return;
    setError(null);
    try {
      // The number in the address's country (its Markets phone code) unless typed with "+".
      const phoneCode = countries.find((c) => c.code === point.country)?.phone_code ?? country?.phone_code ?? "+";
      unwrap(await api.core.POST("/api/v1/markets/waitlist", { body: { phone: e164(phoneCode, phone), lat: point.lat, lng: point.lng } }));
      setDone(true);
    } catch (e) {
      setError(errorMessage((e as { body?: unknown }).body, t("app.out_of_area.failed")));
    }
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: color.porcelain }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, padding: space[5] }}>
        <Icon name="pin" size={20} stroke={color.peacock} />
        <Text style={type.label}>{place && point ? (point.label || t("app.home.current_location")) : ""}</Text>
      </View>
      <View style={{ flex: 1, padding: space[5], justifyContent: "center", gap: space[4] }}>
        <Icon name="map" size={56} stroke={color.peacock} />
        <Txt variant="h1" accessibilityRole="header">
          {place ? t("app.out_of_area.title", { place }) : t("app.out_of_area.title_here")}
        </Txt>
        <Txt style={{ color: color.muted }}>
          {cities.length ? `${t("app.out_of_area.cooking_in", { cities: cities.join(", ") })} ` : ""}{t("app.out_of_area.leave_number")}
        </Txt>
        {done ? (
          <Txt variant="label" style={{ color: color.peacock }}>{place ? t("app.out_of_area.thanks", { place }) : t("app.out_of_area.thanks_here")}</Txt>
        ) : (
          <>
            <Input label={t("signin.mobile")} keyboardType="phone-pad" value={phone} onChangeText={setPhone} error={error ?? undefined} />
            <Button title={t("app.out_of_area.notify")} size="lg" block disabled={!point || phone.replace(/\D/g, "").length < 8} onPress={join} />
          </>
        )}
        <Pressable testID="try-another" accessibilityRole="link" onPress={() => router.replace("/home")}
          style={{ minHeight: 44, justifyContent: "center", marginTop: space[3] }}>
          <Text style={[type.label, { color: color.peacock, textAlign: "center" }]}>{t("home.try_another")}</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}
