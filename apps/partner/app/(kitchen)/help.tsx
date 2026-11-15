// Help and settings: ask BhojanGo to call you back (B3: a ticket in the admin
// support console), this tablet (kitchen, the alert sound, the language: the
// country's languages from Markets), sign out.
import { api, ApiError, type CoreSchemas, field, LanguagePicker, type, unwrap, useI18n, useSession } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, useWindowDimensions, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useBoard } from "../../lib/board";
import { useKitchen } from "../../lib/data";
import { Btn, color, radius, t } from "../../lib/ui";

export default function Help() {
  const { kitchen, kitchens } = useKitchen();
  const user = useSession((s) => s.user);
  const signOut = useSession((s) => s.signOut);
  const { muted, mute } = useBoard();
  const { t: tr } = useI18n();
  const { width } = useWindowDimensions();
  const stacked = width < 900; // a phone held sideways: one column
  return (
    <SafeAreaView testID="help-screen" edges={["top", "right"]} style={{ flex: 1 }}>
      <View style={s.header}><Text accessibilityRole="header" style={t.h1}>{tr("partner.help.title")}</Text></View>
      <ScrollView contentContainerStyle={{ padding: stacked ? 16 : 24, gap: 16, flexDirection: stacked ? "column" : "row", alignItems: stacked ? "stretch" : "flex-start" }}>
        {kitchen ? <CallBack restaurantId={kitchen.id} /> : null}
        <View style={{ flex: 1, gap: 16 }}>
          <View style={s.panel}>
            <Text style={type.h3}>{tr("partner.help.tablet")}</Text>
            <Text style={t.body}>{tr("partner.help.signed_in_as", { kitchen: kitchen?.name ?? "", name: user?.full_name ?? "" })}</Text>
            <Text style={t.muted}>{tr("partner.help.rings")}</Text>
            <Btn testID="mute" title={muted ? tr("partner.help.unmute") : tr("partner.help.mute")} onPress={() => mute(!muted)} />
            {kitchens && kitchens.length > 1 ? <Btn title={tr("partner.help.switch")} onPress={() => router.replace("/kitchens")} /> : null}
            <Btn testID="sign-out" title={tr("partner.help.sign_out")} kind="danger" onPress={async () => { await signOut(); router.replace("/sign-in"); }} />
            <Text style={t.muted}>{tr("partner.help.sign_out_note")}</Text>
          </View>
          <View testID="language-section" style={s.panel}>
            <Text accessibilityRole="header" style={type.h3}>{tr("partner.help.language")}</Text>
            <LanguagePicker />
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

type Ticket = CoreSchemas["TicketOut"];
const TOPICS = ["order", "payout", "menu", "account", "other"] as const;

/** Ask BhojanGo to call the kitchen back: it lands in the admin support console. */
function CallBack({ restaurantId }: { restaurantId: string }) {
  const { t: tr } = useI18n();
  const [open, setOpen] = useState<Ticket | null>(null);
  const [topic, setTopic] = useState<(typeof TOPICS)[number]>("order");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const path = { params: { path: { restaurant_id: restaurantId } } };
  const load = useCallback(async () => {
    try {
      return unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/callback", { params: { path: { restaurant_id: restaurantId } } }));
    } catch {
      return null;
    }
  }, [restaurantId]);
  useEffect(() => {
    let live = true;
    load().then((t) => live && setOpen(t ?? null)).catch(() => undefined);
    return () => {
      live = false;
    };
  }, [load]);

  async function ask() {
    setBusy(true);
    setError(null);
    try {
      setOpen(unwrap(await api.core.POST("/api/v1/restaurants/{restaurant_id}/callback", { ...path, body: { topic, note: note.trim() || null } })));
      setNote("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : tr("partner.help.callback_failed"));
    } finally {
      setBusy(false);
    }
  }

  const topicLabel = (k: string) => ((TOPICS as readonly string[]).includes(k) ? tr(`partner.help.topics.${k}`) : k);
  return (
    <View style={[s.panel, { flex: 1 }]} accessibilityLabel={tr("partner.help.support")}>
      <Text style={type.h3}>{tr("partner.help.support")}</Text>
      {open ? (
        <>
          <View style={s.done}>
            <Text style={[type.label, { color: color.peacockDeep }]}>{tr("partner.help.call_back_title")}</Text>
            <Text style={t.body}>{tr("partner.help.call_back_body")}</Text>
            <Text style={t.muted}>
              {tr("partner.help.about", { topic: topicLabel(open.topic) })}{open.note ? ` · “${open.note}”` : ""}
            </Text>
          </View>
          <Text style={t.muted}>{tr("partner.help.ask_again")}</Text>
        </>
      ) : (
        <Text style={t.body}>{tr("partner.help.ask_intro")}</Text>
      )}
      <View accessibilityRole="radiogroup" accessibilityLabel={tr("partner.help.what_about")} style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        {TOPICS.map((k) => (
          <Pressable key={k} accessibilityRole="radio" accessibilityState={{ checked: topic === k }} onPress={() => setTopic(k)}
            style={[s.chip, topic === k && { borderColor: color.peacock, backgroundColor: color.peacockMist }]}>
            <Text style={type.label}>{topicLabel(k)}</Text>
          </Pressable>
        ))}
      </View>
      <TextInput disableFullscreenUI testID="callback-note" accessibilityLabel={tr("partner.help.note")} value={note} onChangeText={setNote} maxLength={300}
        placeholder={tr("partner.help.note")} placeholderTextColor={color.muted} style={[field.body, s.input]} />
      {error ? <Text style={[type.small, { color: color.chili }]}>{error}</Text> : null}
      <Btn testID="callback-ask" title={open ? tr("partner.help.update_request") : tr("partner.help.request")} kind="primary" busy={busy} onPress={ask} />
      <Text style={t.muted}>{tr("partner.help.refund_note")}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  done: { padding: 16, borderRadius: radius.card, backgroundColor: color.peacockMist, gap: 6 },
  chip: { paddingHorizontal: 16, height: 48, justifyContent: "center", borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.line, backgroundColor: color.white },
  input: { height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: 16, backgroundColor: color.white },
  header: { height: 80, paddingHorizontal: 24, backgroundColor: color.white, borderBottomWidth: 1, borderBottomColor: color.line, justifyContent: "center" },
  panel: { backgroundColor: color.white, borderRadius: radius.card, borderWidth: 1, borderColor: color.line, padding: 20, gap: 12 },
});
