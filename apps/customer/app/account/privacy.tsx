// Privacy and your data (WebProfile): download everything the account holds
// (a JSON file through the share sheet), or delete the account after a clear
// confirmation that says what goes and what stays.
import { Button, color, SafeAreaView, Sheet, space, type, useI18n, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useState } from "react";
import { ScrollView, Text, View } from "react-native";

import { shareMyData } from "../../lib/account";
import { ScreenBar, Section, ui } from "../../lib/account-ui";

export default function Privacy() {
  const { t } = useI18n();
  const deleteAccount = useSession((s) => s.deleteAccount);
  const [busy, setBusy] = useState<"export" | "delete" | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  async function exportData() {
    setBusy("export");
    setProblem(null);
    try {
      await shareMyData(t("account.privacy.download"));
    } catch {
      setProblem(t("account.privacy.failed"));
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    setBusy("delete");
    setProblem(null);
    try {
      await deleteAccount(); // signs out on this phone too
      setConfirming(false);
      router.replace("/sign-in");
    } catch {
      setProblem(t("account.privacy.failed"));
      setConfirming(false);
      setBusy(null);
    }
  }

  return (
    <SafeAreaView style={ui.screen} edges={["top", "left", "right"]}>
      <ScreenBar title={t("account.privacy.title")} testID="privacy-title" />
      <ScrollView contentContainerStyle={ui.scroll}>
        <Section>
          <Button testID="download-data" title={busy === "export" ? t("account.privacy.downloading") : t("account.privacy.download")}
            variant="secondary" block loading={busy === "export"} disabled={busy !== null} onPress={exportData} />
          <Button testID="delete-account" title={t("account.privacy.delete")} variant="danger" block disabled={busy !== null}
            onPress={() => { setProblem(null); setConfirming(true); }} />
          <Text style={ui.small}>{t("account.privacy.note")}</Text>
          {problem ? <Text accessibilityRole="alert" style={ui.error}>{problem}</Text> : null}
        </Section>
      </ScrollView>

      <Sheet visible={confirming} onClose={() => busy !== "delete" && setConfirming(false)} title={t("account.privacy.confirm_title")}
        footer={
          <View style={{ gap: space[2] }}>
            <Button testID="keep-account" title={t("app.account.keep")} size="lg" block disabled={busy === "delete"} onPress={() => setConfirming(false)} />
            <Button testID="confirm-delete" title={busy === "delete" ? t("account.privacy.deleting") : t("account.privacy.confirm")}
              variant="danger" block loading={busy === "delete"} onPress={remove} />
          </View>
        }>
        <Text testID="delete-body" style={[type.body, { color: color.kohl }]}>{t("account.privacy.confirm_body")}</Text>
      </Sheet>
    </SafeAreaView>
  );
}
