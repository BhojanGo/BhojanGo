// Account pieces the Kitchen and Delivery apps share (R19, app store review):
// - Legal: the country's Privacy policy and Terms of use on the website.
// - Delete account: a confirmation that says what goes and what stays (the
//   customer app's rule, apps/customer/app/account/privacy.tsx), and the server's
//   reasons to wait (money still owed on a payout, orders on their way) in words.
import { useState } from "react";
import { ActivityIndicator, Linking, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { deleteAccountProblem, legalPageUrl } from "./account-text";
import { useI18n } from "./i18n";
import { urls, useSession } from "./session";
import { color, dark, radius } from "./ui/theme";
import { type } from "./ui/type";

export type AccountTone = "light" | "dark";

const TONES = {
  light: { bg: color.white, text: color.kohl, muted: color.muted, line: color.lineStrong, link: color.peacock, danger: color.chili, dangerBg: color.chili },
  dark: { bg: dark.surface, text: dark.text, muted: dark.muted, line: dark.lineStrong, link: dark.link, danger: "#F2B8B5", dangerBg: color.chili },
} as const;

/** The website's Terms or Privacy policy page for a country. */
export function legalUrl(kind: "terms" | "privacy", country?: string | null): string {
  return legalPageUrl(urls.web, kind, country);
}

/** Privacy policy and Terms of use, each opening the country's page on the website. */
export function LegalLinks({ tone = "light", country }: { tone?: AccountTone; country?: string | null }) {
  const { t } = useI18n();
  const c = TONES[tone];
  const rows = [
    { key: "privacy" as const, title: t("signin.privacy") },
    { key: "terms" as const, title: t("legal.terms") },
  ];
  return (
    <View accessibilityLabel={t("account.legal.title")}>
      {rows.map((r, i) => (
        <Pressable key={r.key} testID={`legal-${r.key}`} accessibilityRole="link" accessibilityHint={t("account.legal.opens")}
          onPress={() => void Linking.openURL(legalUrl(r.key, country))}
          style={[s.row, i < rows.length - 1 && { borderBottomWidth: 1, borderBottomColor: c.line }]}>
          <Text style={[type.label, { color: c.link, flex: 1 }]}>{r.title}</Text>
          <Text style={[type.small, { color: c.muted }]}>{t("account.legal.opens")}</Text>
        </Pressable>
      ))}
    </View>
  );
}

/**
 * "Delete my account" and its confirmation sheet. `body` says what goes and what
 * stays for this kind of account; `before` runs first (the Delivery app stops
 * sharing its location) and `undo` runs if the server refused (it starts again).
 */
export function DeleteAccount({ tone = "light", body, note, before, undo, onDeleted }: {
  tone?: AccountTone;
  body: string;
  note: string;
  before?: () => Promise<unknown>;
  undo?: () => Promise<unknown>;
  onDeleted: () => void;
}) {
  const { t } = useI18n();
  const deleteAccount = useSession((st) => st.deleteAccount);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const c = TONES[tone];
  // The sheet clears the system navigation bar and scrolls when the screen is short (a tablet held
  // sideways): the delete button must always be reachable (R19).
  const insets = useSafeAreaInsets();

  async function remove() {
    setBusy(true);
    setProblem(null);
    try {
      await before?.();
      await deleteAccount(); // signs out on this phone too
      setConfirming(false);
      onDeleted();
    } catch (e) {
      await undo?.().catch(() => undefined);
      setProblem(deleteAccountProblem(e, t));
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ gap: 8 }}>
      <Pressable testID="delete-account" accessibilityRole="button" disabled={busy}
        onPress={() => { setProblem(null); setConfirming(true); }} style={[s.btn, { borderColor: c.line, backgroundColor: c.bg }]}>
        <Text style={[type.label, { color: c.danger }]}>{t("account.privacy.delete")}</Text>
      </Pressable>
      <Text style={[type.small, { color: c.muted }]}>{note}</Text>
      {problem ? <Text testID="delete-problem" accessibilityRole="alert" style={[type.small, { color: c.danger }]}>{problem}</Text> : null}

      <Modal transparent visible={confirming} animationType="slide" onRequestClose={() => { if (!busy) setConfirming(false); }}>
        <Pressable style={s.scrim} onPress={() => { if (!busy) setConfirming(false); }} accessibilityLabel={t("common.close")} />
        <ScrollView accessibilityViewIsModal testID="delete-sheet" style={[s.sheetBox, { backgroundColor: c.bg }]}
          contentContainerStyle={[s.sheet, { paddingBottom: 32 + insets.bottom }]}>
          <Text accessibilityRole="header" style={[type.h3, { color: c.text }]}>{t("account.privacy.confirm_title")}</Text>
          <Text testID="delete-body" style={[type.body, { color: c.text }]}>{body}</Text>
          <Pressable testID="keep-account" accessibilityRole="button" disabled={busy} onPress={() => setConfirming(false)}
            style={[s.btn, s.big, { backgroundColor: color.peacock, borderColor: color.peacock }]}>
            <Text style={[type.label, { color: color.white }]}>{t("app.account.keep")}</Text>
          </Pressable>
          <Pressable testID="confirm-delete" accessibilityRole="button" disabled={busy} onPress={() => void remove()}
            accessibilityState={{ busy }} style={[s.btn, { borderColor: c.dangerBg, backgroundColor: c.bg }]}>
            {busy ? <ActivityIndicator color={c.danger} /> : null}
            <Text style={[type.label, { color: c.danger }]}>{busy ? t("account.privacy.deleting") : t("account.privacy.confirm")}</Text>
          </Pressable>
        </ScrollView>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  row: { minHeight: 52, flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12 },
  btn: { minHeight: 48, borderRadius: radius.pill, borderWidth: 1.5, flexDirection: "row", gap: 8, alignItems: "center", justifyContent: "center", paddingHorizontal: 20 },
  big: { minHeight: 56 },
  scrim: { flex: 1, backgroundColor: "rgba(17, 20, 24, 0.4)" },
  sheetBox: { flexGrow: 0, maxHeight: "85%", borderTopLeftRadius: 28, borderTopRightRadius: 28 },
  sheet: { padding: 24, gap: 16 },
});
