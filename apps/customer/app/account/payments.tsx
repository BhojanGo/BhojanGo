// Payment methods (WebProfile): the saved cards (brand, last four, expiry;
// make default, remove) and the ways to pay the country offers (Markets
// payment_methods). Card numbers never touch BhojanGo: real cards are added in
// the payment provider's form at checkout. On a test site you can save a test
// card here (a fake token with the brand, last 4 digits and expiry).
import { appEnv, Button, Chip, color, Input, isTestEnvironment, space, type, useCountry, useI18n } from "@bhojango/mobile-core";
import { useCallback, useEffect, useState } from "react";
import { Alert, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  addTestCard, brandName, listPaymentMethods, makeDefaultPaymentMethod, payLabel, removePaymentMethod,
  type PaymentMethod,
} from "../../lib/account";
import { LinkButton, Row, ScreenBar, Section, Status, ui } from "../../lib/account-ui";

const TEST_SITE = isTestEnvironment(appEnv());
const BRANDS = ["visa", "mastercard", "amex", "rupay", "discover"];

function AddCard({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const { t } = useI18n();
  const now = new Date();
  const [brand, setBrand] = useState(BRANDS[0]!);
  const [last4, setLast4] = useState("");
  const [month, setMonth] = useState(String(now.getMonth() + 1));
  const [year, setYear] = useState(String(now.getFullYear() + 2));
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function save() {
    const m = Number(month);
    const y = Number(year);
    const expired = !(m >= 1 && m <= 12) || y < now.getFullYear() || (y === now.getFullYear() && m < now.getMonth() + 1);
    if (!/^\d{4}$/.test(last4) || expired) return setProblem(t("account.payments.invalid"));
    setBusy(true);
    setProblem(null);
    try {
      await addTestCard({ brand, last4, exp_month: m, exp_year: y });
      onDone();
    } catch {
      setProblem(t("account.profile.save_failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title={t("account.payments.add_title")} note={t("account.payments.add_note")} testID="add-card">
      <Text style={type.label}>{t("account.payments.brand")}</Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space[2] }}>
        {BRANDS.map((b) => <Chip key={b} label={brandName(b)} selected={b === brand} onPress={() => setBrand(b)} />)}
      </View>
      <Input testID="card-last4" label={t("account.payments.last4")} value={last4} keyboardType="number-pad" maxLength={4}
        onChangeText={(v) => setLast4(v.replace(/\D/g, "").slice(0, 4))} />
      <View style={{ flexDirection: "row", gap: space[3] }}>
        <View style={{ flex: 1 }}>
          <Input label={t("account.payments.exp_month")} value={month} keyboardType="number-pad" maxLength={2} onChangeText={(v) => setMonth(v.replace(/\D/g, ""))} />
        </View>
        <View style={{ flex: 1 }}>
          <Input label={t("account.payments.exp_year")} value={year} keyboardType="number-pad" maxLength={4} onChangeText={(v) => setYear(v.replace(/\D/g, ""))} />
        </View>
      </View>
      {problem ? <Text accessibilityRole="alert" style={ui.error}>{problem}</Text> : null}
      <Button testID="save-card" title={t("account.payments.save")} block loading={busy} onPress={save} />
      <Button title={t("common.cancel")} variant="secondary" block onPress={onCancel} />
    </Section>
  );
}

export default function Payments() {
  const { t } = useI18n();
  const { country } = useCountry();
  const [list, setList] = useState<PaymentMethod[] | null | "error">(null);
  const [adding, setAdding] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const load = useCallback(() => {
    listPaymentMethods().then(setList).catch(() => setList("error"));
  }, []);
  useEffect(load, [load]);

  async function act(m: PaymentMethod, what: "default" | "remove") {
    setProblem(null);
    try {
      if (what === "default") await makeDefaultPaymentMethod(m.id);
      else await removePaymentMethod(m.id);
      load();
    } catch {
      setProblem(t("account.profile.save_failed"));
    }
  }

  function confirmRemove(m: PaymentMethod) {
    Alert.alert(t("account.payments.confirm_remove", { brand: brandName(m.brand), last4: m.last4 }), undefined, [
      { text: t("common.cancel"), style: "cancel" },
      { text: t("account.payments.remove"), style: "destructive", onPress: () => void act(m, "remove") },
    ]);
  }

  const offered = country?.payment_methods ?? [];
  return (
    <SafeAreaView style={ui.screen} edges={["top", "left", "right"]}>
      <ScreenBar title={t("account.payments.title")} testID="payments-title" />
      <ScrollView contentContainerStyle={ui.scroll} keyboardShouldPersistTaps="handled">
        <Section title={t("app.payments.saved")} note={t("account.payments.note")} testID="saved-cards">
          <Status loading={list === null} error={list === "error" ? t("account.payments.unavailable") : null} onRetry={load} />
          {Array.isArray(list) && !list.length ? <Text testID="no-cards" style={ui.muted}>{t("account.payments.empty")}</Text> : null}
          {Array.isArray(list)
            ? list.map((m, i) => (
              <View key={m.id} testID={`card-${m.last4}`}>
                <Row label={t("account.payments.card")} last={i === list.length - 1}
                  value={t("account.payments.ending", { brand: brandName(m.brand), last4: m.last4 })}
                  note={[t("account.payments.expires", { month: String(m.exp_month).padStart(2, "0"), year: String(m.exp_year).slice(-2) }),
                    m.is_default ? t("account.payments.default") : null].filter(Boolean).join(" · ")}
                  action={
                    <View style={{ alignItems: "flex-end", gap: 4 }}>
                      {!m.is_default ? <LinkButton title={t("account.payments.make_default")} onPress={() => void act(m, "default")} /> : null}
                      <LinkButton testID={`remove-card-${m.last4}`} danger title={t("account.payments.remove")} onPress={() => confirmRemove(m)} />
                    </View>
                  } />
              </View>
            ))
            : null}
          {problem ? <Text accessibilityRole="alert" style={ui.error}>{problem}</Text> : null}
          {!TEST_SITE ? <Text style={ui.small}>{t("account.payments.live_note")}</Text> : null}
          {TEST_SITE && !adding ? <LinkButton testID="add-card-open" title={`+ ${t("account.payments.add")}`} onPress={() => setAdding(true)} /> : null}
        </Section>

        {adding ? <AddCard onCancel={() => setAdding(false)} onDone={() => { setAdding(false); load(); }} /> : null}

        {country && offered.length ? (
          <Section title={t("app.payments.offered", { country: country.name })} note={t("app.payments.offered_note")} testID="offered-methods">
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space[2] }}>
              {offered.map((p) => (
                <View key={p} testID={`method-${p}`} style={{ paddingHorizontal: 14, height: 36, justifyContent: "center", borderRadius: 999, backgroundColor: color.peacockMist }}>
                  <Text style={[type.label, { color: color.peacockDeep }]}>{payLabel(t, p)}</Text>
                </View>
              ))}
            </View>
          </Section>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}
