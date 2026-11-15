// Notifications (WebProfile): order updates, receipts and account, offers, each
// by push, SMS and email. A switch saves at once (and goes back if it fails).
import { color, textFont, useI18n } from "@bhojango/mobile-core";
import { useCallback, useEffect, useState } from "react";
import { ScrollView, Switch, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { getPrefs, NOTIFY_CHANNELS, NOTIFY_KINDS, setPref, type NotifyChannel, type NotifyKind, type Prefs } from "../../lib/account";
import { ScreenBar, Section, Status, ui } from "../../lib/account-ui";

export default function Notifications() {
  const { t } = useI18n();
  const [prefs, setPrefs] = useState<Prefs | null | "error">(null);
  const [problem, setProblem] = useState<string | null>(null);

  const load = useCallback(() => {
    getPrefs().then(setPrefs).catch(() => setPrefs("error"));
  }, []);
  useEffect(load, [load]);

  async function flip(kind: NotifyKind, channel: NotifyChannel, value: boolean) {
    if (!prefs || prefs === "error") return;
    const before = prefs;
    setProblem(null);
    setPrefs({ ...prefs, [kind]: { ...prefs[kind], [channel]: value } }); // at once; back if it fails
    try {
      setPrefs(await setPref(kind, channel, value));
    } catch {
      setPrefs(before);
      setProblem(t("account.profile.save_failed"));
    }
  }

  return (
    <SafeAreaView style={ui.screen} edges={["top", "left", "right"]}>
      <ScreenBar title={t("account.notifications.title")} testID="notifications-title" />
      <ScrollView contentContainerStyle={ui.scroll}>
        <Status loading={prefs === null} error={prefs === "error" ? t("account.notifications.unavailable") : null} onRetry={() => { setPrefs(null); load(); }} />
        {prefs && prefs !== "error"
          ? NOTIFY_KINDS.map((k) => (
            <Section key={k} title={t(`account.notifications.${k}`)} note={t(`account.notifications.${k}_note`)} testID={`notify-${k}`}>
              {NOTIFY_CHANNELS.map((c) => {
                const on = prefs[k]?.[c] ?? false;
                const label = t("account.notifications.toggle", { kind: t(`account.notifications.${k}`), channel: t(`account.notifications.${c}`) });
                return (
                  <View key={c} style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: 44 }}>
                    <Text style={[textFont("600"), { fontSize: 16, color: color.kohl }]}>{t(`account.notifications.${c}`)}</Text>
                    <Switch testID={`notify-${k}-${c}`} accessibilityLabel={label} value={on} onValueChange={(v) => void flip(k, c, v)}
                      trackColor={{ true: color.peacock, false: color.lineStrong }} thumbColor={color.white} />
                  </View>
                );
              })}
            </Section>
          ))
          : null}
        {problem ? <Text accessibilityRole="alert" style={ui.error}>{problem}</Text> : null}
      </ScrollView>
    </SafeAreaView>
  );
}
