// Help: ask BhojanGo to call you back (B3: a ticket in the admin support
// console), which kitchen this tablet runs, the alert sound, sign out.
import { api, ApiError, unwrap, useSession, type CoreSchemas } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useBoard } from "../../lib/board";
import { useKitchen } from "../../lib/data";
import { Btn, color, radius, t, textFont } from "../../lib/ui";

export default function Help() {
  const { kitchen, kitchens } = useKitchen();
  const user = useSession((s) => s.user);
  const signOut = useSession((s) => s.signOut);
  const { muted, mute } = useBoard();
  return (
    <SafeAreaView edges={["top", "right"]} style={{ flex: 1 }}>
      <View style={s.header}><Text accessibilityRole="header" style={t.h1}>Help</Text></View>
      <View style={{ padding: 24, gap: 16, flexDirection: "row", alignItems: "flex-start" }}>
        {kitchen ? <CallBack restaurantId={kitchen.id} /> : null}
        <View style={[s.panel, { flex: 1 }]}>
          <Text style={[textFont("800"), { fontSize: 17 }]}>This tablet</Text>
          <Text style={t.body}>{kitchen?.name} · signed in as {user?.full_name}</Text>
          <Text style={t.muted}>New orders ring until you accept or reject them.</Text>
          <Btn title={muted ? "Turn the new-order alert back on" : "Mute the new-order alert"} onPress={() => mute(!muted)} />
          {kitchens && kitchens.length > 1 ? <Btn title="Switch kitchen" onPress={() => router.replace("/kitchens")} /> : null}
          <Btn title="Sign out" kind="danger" onPress={async () => { await signOut(); router.replace("/sign-in"); }} />
        </View>
      </View>
    </SafeAreaView>
  );
}

type Ticket = CoreSchemas["TicketOut"];
const TOPICS = [
  { key: "order", label: "An order" }, { key: "payout", label: "A payout" }, { key: "menu", label: "The menu" },
  { key: "account", label: "The account" }, { key: "other", label: "Something else" },
] as const;

/** Ask BhojanGo to call the kitchen back: it lands in the admin support console. */
function CallBack({ restaurantId }: { restaurantId: string }) {
  const [open, setOpen] = useState<Ticket | null>(null);
  const [topic, setTopic] = useState<(typeof TOPICS)[number]["key"]>("order");
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
      setError(e instanceof ApiError ? e.message : "Couldn't send your request. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={[s.panel, { flex: 1 }]} accessibilityLabel="Partner support">
      <Text style={[textFont("800"), { fontSize: 17 }]}>Partner support</Text>
      {open ? (
        <>
          <View style={s.done}>
            <Text style={[textFont("800"), { fontSize: 16, color: color.peacockDeep }]}>{"We'll call you back"}</Text>
            <Text style={t.body}>On the number this tablet signed in with, usually within 15 minutes during opening hours.</Text>
            <Text style={t.muted}>About: {TOPICS.find((x) => x.key === open.topic)?.label ?? open.topic}{open.note ? ` · “${open.note}”` : ""}</Text>
          </View>
          <Text style={t.muted}>Something else came up? Change the topic and ask again; we keep one request open.</Text>
        </>
      ) : (
        <Text style={t.body}>A problem with an order, a payout or the menu? Ask us to call you back.</Text>
      )}
      <View accessibilityRole="radiogroup" accessibilityLabel="What is it about?" style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        {TOPICS.map((x) => (
          <Pressable key={x.key} accessibilityRole="radio" accessibilityState={{ checked: topic === x.key }} onPress={() => setTopic(x.key)}
            style={[s.chip, topic === x.key && { borderColor: color.peacock, backgroundColor: color.peacockMist }]}>
            <Text style={[textFont(topic === x.key ? "800" : "600"), { fontSize: 15 }]}>{x.label}</Text>
          </Pressable>
        ))}
      </View>
      <TextInput testID="callback-note" accessibilityLabel="Anything we should know? (optional)" value={note} onChangeText={setNote} maxLength={300}
        placeholder="Anything we should know? (optional)" placeholderTextColor={color.muted} style={[textFont("600"), s.input]} />
      {error ? <Text style={[textFont("600"), { color: color.chili }]}>{error}</Text> : null}
      <Btn title={open ? "Update my request" : "Request a call back"} kind="primary" busy={busy} onPress={ask} />
      <Text style={t.muted}>A rejected or late order shows the reason to the customer and is refunded in full.</Text>
    </View>
  );
}

const s = StyleSheet.create({
  done: { padding: 16, borderRadius: radius.card, backgroundColor: color.peacockMist, gap: 6 },
  chip: { paddingHorizontal: 16, height: 48, justifyContent: "center", borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.line, backgroundColor: color.white },
  input: { height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: 16, fontSize: 16, backgroundColor: color.white },
  header: { height: 80, paddingHorizontal: 24, backgroundColor: color.white, borderBottomWidth: 1, borderBottomColor: color.line, justifyContent: "center" },
  panel: { backgroundColor: color.white, borderRadius: radius.card, borderWidth: 1, borderColor: color.line, padding: 20, gap: 12 },
});
