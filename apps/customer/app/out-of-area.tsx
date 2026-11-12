// CustomerOutOfArea.html: we don't deliver here yet; leave a number to hear when we do.
import { api, Button, color, errorMessage, Input, space, textFont, Txt, unwrap } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../lib/icons";
import { useWhere } from "../lib/where";

export default function OutOfArea() {
  const point = useWhere((s) => s.point);
  // The most specific place we know (a neighbourhood can be outside a served city's zones).
  const place = point?.label?.split("· ")[1] || point?.city || "your area";
  const [phone, setPhone] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function join() {
    if (!point) return;
    setError(null);
    try {
      const digits = phone.replace(/\D/g, "");
      const e164 = phone.trim().startsWith("+") ? `+${digits}` : point.country === "IN" ? `+91${digits}` : `+1${digits}`;
      unwrap(await api.core.POST("/api/v1/markets/waitlist", { body: { phone: e164, lat: point.lat, lng: point.lng } }));
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
          BhojanGo is cooking in Boise and Hyderabad. Leave your number and we&apos;ll text you the day we arrive.
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
