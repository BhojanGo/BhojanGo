// CustomerOutOfArea.html: we don't deliver here yet; leave a number to hear when we do.
import {
  api, Button, color, e164, errorMessage, Input, liveCityNames, space, textFont, Txt, unwrap, useCountry, useI18n,
} from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../lib/icons";
import { useWhere } from "../lib/where";

export default function OutOfArea() {
  const point = useWhere((s) => s.point);
  const { t } = useI18n();
  const { country, countries } = useCountry();
  const cities = liveCityNames(countries); // where we cook now (Markets)
  // The most specific place we know (a neighbourhood can be outside a served city's zones).
  const place = point?.label?.split("· ")[1] || point?.city || "your area";
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
      setError(errorMessage((e as { body?: unknown }).body, "Check the number and try again."));
    }
  }

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: color.porcelain }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8, padding: space[5] }}>
        <Icon name="pin" size={20} stroke={color.peacock} />
        <Text style={[textFont("700"), { fontSize: 15 }]}>{point?.label}</Text>
      </View>
      <View style={{ flex: 1, padding: space[5], justifyContent: "center", gap: space[4] }}>
        <Icon name="map" size={56} stroke={color.peacock} />
        <Txt variant="h1" accessibilityRole="header" style={{ fontSize: 30, lineHeight: 33 }}>
          We&apos;re not in {place} yet
        </Txt>
        <Txt style={{ color: color.muted }}>
          {cities.length ? `${t("app.out_of_area.cooking_in", { cities: cities.join(", ") })} ` : ""}{t("app.out_of_area.leave_number")}
        </Txt>
        {done ? (
          <Txt variant="label" style={{ color: color.peacock }}>Thanks. We&apos;ll text you when we launch in {place}.</Txt>
        ) : (
          <>
            <Input label="Mobile number" keyboardType="phone-pad" value={phone} onChangeText={setPhone} error={error ?? undefined} />
            <Button title="Tell me when you launch" size="lg" block disabled={phone.replace(/\D/g, "").length < 8} onPress={join} />
          </>
        )}
        <Text style={[textFont("700"), { color: color.peacock, textAlign: "center", marginTop: space[4] }]} onPress={() => router.replace("/home")}>
          Try another address
        </Text>
      </View>
    </SafeAreaView>
  );
}
