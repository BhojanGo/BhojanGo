// Account (website parity, WebProfile): your details, then a page each for
// addresses, payment methods, notifications, favourites, language,
// and privacy (download your data, delete your account); Legal (R20: the country's
// Privacy policy and Terms of use on the website, as in the Kitchen and Delivery apps); sign out.
import { Button, color, Input, LANGUAGES, LegalLinks, SafeAreaView, Sheet, space, Txt, useCountry, useI18n, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { ScrollView, Text, View } from "react-native";

import { updateMe } from "../../lib/account";
import { LinkButton, MenuRow, Row, Section, ui } from "../../lib/account-ui";
import { TabEnd, useTabBarSpace } from "../../lib/tabbar";

export default function Account() {
  const { t, language } = useI18n();
  const bottom = useTabBarSpace();
  const user = useSession((s) => s.user);
  const { country } = useCountry(); // the delivery address's country: its legal pages
  const signOut = useSession((s) => s.signOut);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function saveName() {
    if (!name.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      await updateMe({ full_name: name.trim() });
      setEditing(false);
      setMsg({ ok: true, text: t("account.profile.saved") });
    } catch {
      setMsg({ ok: false, text: t("account.profile.save_failed") });
    } finally {
      setBusy(false);
    }
  }

  const languageValue = LANGUAGES[language].name;
  return (
    <SafeAreaView style={ui.screen} edges={["top"]}>
      <ScrollView testID="account-screen" contentContainerStyle={{ padding: space[5], gap: space[4], paddingBottom: bottom }}>
        <Txt variant="h2" accessibilityRole="header">{t("app.account.title")}</Txt>

        <Section title={t("account.profile.details")} testID="account-profile">
          <Row label={t("account.profile.name")} value={user?.full_name ?? ""}
            action={<LinkButton testID="edit-name" title={t("common.edit")} onPress={() => { setName(user?.full_name ?? ""); setMsg(null); setEditing(true); }} />} />
          <Row label={t("account.profile.mobile")} value={user?.phone ?? t("account.profile.not_set")}
            note={user?.is_phone_verified ? t("account.profile.mobile_note") : t("account.profile.mobile_unverified")} />
          <Row label={t("account.profile.email")} value={user?.email ?? t("account.profile.not_set")} note={t("account.profile.email_note")} last />
          <Text style={ui.small}>{t("account.profile.read_only_note")}</Text>
          {msg ? <Text accessibilityRole="alert" style={msg.ok ? ui.ok : ui.error}>{msg.text}</Text> : null}
        </Section>

        <Section style={{ paddingVertical: space[2] }}>
          <MenuRow testID="account-addresses" icon="pin" label={t("account.nav.addresses")} href="/account/addresses" />
          <MenuRow testID="account-payments" icon="bag" label={t("account.nav.payments")} href="/account/payments" />
          <MenuRow testID="account-notifications" icon="message" label={t("account.nav.notifications")} href="/account/notifications" />
          <MenuRow testID="account-favourites" icon="star" label={t("account.nav.favourites")} href="/favourites" />
          <MenuRow testID="account-language" icon="map" label={t("header.language")} value={languageValue} href="/account/language" />
          <MenuRow testID="account-privacy" icon="alert" label={t("account.nav.privacy")} href="/account/privacy" last />
        </Section>

        <Section title={t("account.legal.title")} testID="account-legal">
          <LegalLinks country={country?.code ?? user?.country} />
        </Section>

        <View testID="account-last">
          <Button testID="sign-out" title={t("common.sign_out")} variant="secondary" block
            onPress={async () => { await signOut(); router.replace("/sign-in"); }} />
        </View>
        <TabEnd tab="account" />
      </ScrollView>

      <Sheet visible={editing} onClose={() => setEditing(false)} title={t("account.profile.name_label")}
        footer={
          <View style={{ gap: space[2] }}>
            <Button testID="save-name" title={t("common.save")} size="lg" block loading={busy} disabled={!name.trim()} onPress={saveName} />
            <Button title={t("common.cancel")} variant="secondary" block onPress={() => setEditing(false)} />
          </View>
        }>
        <Input testID="name-input" label={t("account.profile.name")} value={name} onChangeText={setName} maxLength={100} autoComplete="name" autoFocus />
        {msg && !msg.ok ? <Text style={[ui.error, { color: color.chili }]}>{msg.text}</Text> : null}
      </Sheet>
    </SafeAreaView>
  );
}
