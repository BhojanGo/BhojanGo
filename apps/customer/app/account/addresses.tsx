// Saved addresses (WebProfile): the default first, delivery notes, make
// default, edit, delete, add. Making one the default also makes it where the
// app shows food for (and so the country, its languages and prices).
import { Button, color, space, textFont, useI18n } from "@bhojango/mobile-core";
import { router, useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";
import { Alert, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { deleteAddress, followAddress, listAddresses, makeDefaultAddress, type Address } from "../../lib/account";
import { LinkButton, ScreenBar, Section, Status, ui } from "../../lib/account-ui";

export default function Addresses() {
  const { t } = useI18n();
  const [list, setList] = useState<Address[] | null | "error">(null);
  const [problem, setProblem] = useState<string | null>(null);

  const load = useCallback(() => {
    listAddresses().then(setList).catch(() => setList("error"));
  }, []);
  useFocusEffect(load);

  async function makeDefault(a: Address) {
    setProblem(null);
    try {
      await makeDefaultAddress(a.id);
      followAddress(a);
      load();
    } catch {
      setProblem(t("account.profile.save_failed"));
    }
  }

  function confirmDelete(a: Address) {
    Alert.alert(t("account.addresses.confirm_delete", { label: a.label || a.street }), undefined, [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("account.addresses.delete"), style: "destructive",
        onPress: () => void deleteAddress(a.id).then(load).catch(() => setProblem(t("account.profile.save_failed"))),
      },
    ]);
  }

  const items = Array.isArray(list) ? [...list].sort((a, b) => Number(!!b.is_default) - Number(!!a.is_default)) : [];
  return (
    <SafeAreaView style={ui.screen} edges={["top", "left", "right"]}>
      <ScreenBar title={t("account.addresses.title")} testID="addresses-title" />
      <ScrollView contentContainerStyle={ui.scroll}>
        <Status loading={list === null} error={list === "error" ? t("account.addresses.unavailable") : null} onRetry={load} />
        {Array.isArray(list) && !list.length ? <Text testID="no-addresses" style={ui.muted}>{t("account.addresses.empty")}</Text> : null}
        {items.map((a, i) => (
          <Section key={a.id} testID={`address-${i}`} style={a.is_default ? { borderWidth: 1.5, borderColor: color.peacock, backgroundColor: color.peacockMist } : undefined}>
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: space[2] }}>
              <Text numberOfLines={1} style={[ui.h2, { flex: 1 }]}>{a.label || a.street}</Text>
              {a.is_default ? (
                <Text testID="address-default" style={[textFont("800"), { fontSize: 12, letterSpacing: 0.6, textTransform: "uppercase", color: color.peacockDeep }]}>
                  {t("account.addresses.default")}
                </Text>
              ) : (
                <LinkButton testID={`address-${i}-make-default`} title={t("account.addresses.make_default")} onPress={() => void makeDefault(a)} />
              )}
            </View>
            <Text style={[textFont("400"), { fontSize: 15, color: color.kohl }]}>{[a.street, a.city, a.state].filter(Boolean).join(", ")} {a.postal_code}</Text>
            {a.delivery_notes ? <Text style={ui.small}>{a.delivery_notes}</Text> : null}
            <View style={{ flexDirection: "row", gap: space[5] }}>
              <LinkButton testID={`address-${i}-edit`} title={t("account.addresses.edit")} onPress={() => router.push(`/account/address?id=${a.id}`)} />
              <LinkButton testID={`address-${i}-delete`} danger title={t("account.addresses.delete")} onPress={() => confirmDelete(a)} />
            </View>
          </Section>
        ))}
        {problem ? <Text accessibilityRole="alert" style={ui.error}>{problem}</Text> : null}
        {list !== null && list !== "error" ? (
          <Button testID="add-address" title={`+ ${t("account.addresses.add")}`} variant="secondary" block onPress={() => router.push("/account/address")} />
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}
