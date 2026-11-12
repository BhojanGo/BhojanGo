// Quick messages between the customer and the rider during an active order (B2).
// Preset messages plus a short text, live over the order's tracking socket
// (realtime) with a push when the app is closed. The button only shows while
// the conversation is open (a rider assigned, not yet delivered); nobody sees
// a phone number.
import { unwrap, type CoreSchemas } from "@bhojango/api-client";
import { useCallback, useEffect, useRef, useState } from "react";
import { KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { api, wsUrl } from "./session";
import { color, dark, radius, textFont } from "./ui/theme";

type Chat = CoreSchemas["QuickMessagesOut"];
type Message = CoreSchemas["QuickMessage"];

const MAX = 140;

async function fetchChat(orderId: string): Promise<Chat | null> {
  try {
    return unwrap(await api.core.GET("/api/v1/orders/{order_id}/messages", { params: { path: { order_id: orderId } } }));
  } catch {
    return null; // not ours, or the network: the button just stays hidden
  }
}

/** The conversation for an order: loads it, follows it live, and sends. */
export function useQuickMessages(orderId: string | undefined) {
  const [chat, setChat] = useState<Chat | null>(null);
  const [unread, setUnread] = useState(0);
  const seen = useRef(new Set<string>());

  const apply = useCallback((c: Chat | null) => {
    if (!c) return;
    c.messages.forEach((m) => seen.current.add(m.id));
    setChat(c);
  }, []);
  const load = useCallback(async () => {
    if (orderId) apply(await fetchChat(orderId));
  }, [orderId, apply]);

  useEffect(() => {
    if (!orderId) return;
    let live = true;
    fetchChat(orderId).then((c) => live && apply(c)).catch(() => undefined);
    const ws = new WebSocket(wsUrl(`/ws/track/${orderId}`));
    ws.onmessage = (e) => {
      const m = JSON.parse(String(e.data)) as { type: string; payload: { id: string; sender_role: string; text: string; at: string } };
      if (m.type === "status_change" || m.type === "rider_assigned") void load();
      if (m.type !== "chat_message" || seen.current.has(m.payload.id)) return;
      seen.current.add(m.payload.id);
      setChat((c) => {
        if (!c) return c;
        const mine = m.payload.sender_role === c.me;
        if (!mine) setUnread((n) => n + 1);
        const msg = { id: m.payload.id, mine, sender_role: m.payload.sender_role, text: m.payload.text, at: m.payload.at } as Message;
        return { ...c, messages: [...c.messages, msg] };
      });
    };
    const poll = setInterval(() => void load(), 30000); // the socket can drop on mobile networks
    return () => {
      live = false;
      clearInterval(poll);
      ws.close();
    };
  }, [orderId, load, apply]);

  const send = useCallback(async (body: { preset: string } | { text: string }) => {
    if (!orderId) return;
    const m = unwrap(await api.core.POST("/api/v1/orders/{order_id}/messages", { params: { path: { order_id: orderId } }, body }));
    if (seen.current.has(m.id)) return;
    seen.current.add(m.id);
    setChat((c) => (c ? { ...c, messages: [...c.messages, m] } : c));
  }, [orderId]);

  return { chat, unread, markRead: () => setUnread(0), send, reload: load };
}

/** A button that opens the conversation; renders nothing while it's closed. */
export function QuickChat({ orderId, tone = "light", render }: {
  orderId: string | undefined;
  tone?: "light" | "dark";
  /** Draw the button yourself: called with what opens the chat and the unread count. */
  render?: (open: () => void, unread: number, name: string) => React.ReactNode;
}) {
  const { chat, unread, markRead, send } = useQuickMessages(orderId);
  const [visible, setVisible] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const list = useRef<{ scrollToEnd: (o?: { animated?: boolean }) => void } | null>(null);
  if (!chat?.open) return null;
  const c = tone === "dark"
    ? { bg: dark.surface, text: dark.text, muted: dark.muted, line: dark.lineStrong, field: dark.ground, theirs: dark.raised, chip: dark.raised }
    : { bg: color.white, text: color.kohl, muted: color.muted, line: color.lineStrong, field: color.white, theirs: color.porcelain, chip: color.peacockMist };
  const open = () => {
    markRead();
    setVisible(true);
  };
  async function go(body: { preset: string } | { text: string }) {
    setBusy(true);
    setError(null);
    try {
      await send(body);
      if ("text" in body) setText("");
      setTimeout(() => list.current?.scrollToEnd({ animated: true }), 50);
    } catch (e) {
      setError((e as Error).message || "Couldn't send. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {render ? render(open, unread, chat.other_name) : (
        <Pressable testID="chat-open" accessibilityRole="button" onPress={open}
          accessibilityLabel={`Message ${chat.other_name}${unread ? `, ${unread} new` : ""}`}
          style={[s.round, { borderColor: c.line }]}>
          <Text style={[textFont("800"), { fontSize: 13, color: c.text }]}>Message</Text>
          {unread ? <View style={s.badge}><Text style={[textFont("800"), { color: color.white, fontSize: 11 }]}>{unread}</Text></View> : null}
        </Pressable>
      )}
      <Modal transparent visible={visible} animationType="slide" onRequestClose={() => setVisible(false)}>
        <Pressable style={s.scrim} onPress={() => setVisible(false)} accessibilityLabel="Close messages" />
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={[s.sheet, { backgroundColor: c.bg }]}>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <View style={{ flex: 1 }}>
              <Text accessibilityRole="header" style={[textFont("800"), { fontSize: 20, color: c.text }]}>Message {chat.other_name}</Text>
              <Text style={[textFont("400"), { fontSize: 13, color: c.muted, marginTop: 2 }]}>Your number stays private. Messages close once the order is delivered.</Text>
            </View>
            <Pressable accessibilityRole="button" onPress={() => setVisible(false)} style={{ padding: 8 }}>
              <Text style={[textFont("700"), { color: c.muted }]}>Close</Text>
            </Pressable>
          </View>
          <ScrollView ref={list as never} style={{ maxHeight: 260 }} contentContainerStyle={{ gap: 8, paddingVertical: 12 }}
            onContentSizeChange={() => list.current?.scrollToEnd({ animated: false })}>
            {chat.messages.length === 0 ? (
              <Text style={[textFont("400"), { color: c.muted, fontSize: 14 }]}>No messages yet. Tap a quick message or write a short note.</Text>
            ) : chat.messages.map((m) => (
              <View key={m.id} accessibilityLabel={`${m.mine ? "You" : chat.other_name}: ${m.text}`}
                style={[s.bubble, m.mine ? { alignSelf: "flex-end", backgroundColor: color.peacock } : { alignSelf: "flex-start", backgroundColor: c.theirs }]}>
                <Text style={[textFont("600"), { fontSize: 15, color: m.mine ? color.white : c.text }]}>{m.text}</Text>
              </View>
            ))}
          </ScrollView>
          <View style={s.chips}>
            {chat.presets.map((p) => (
              <Pressable key={p.key} accessibilityRole="button" disabled={busy} onPress={() => void go({ preset: p.key })}
                style={[s.chip, { backgroundColor: c.chip }]}>
                <Text style={[textFont("700"), { fontSize: 13, color: tone === "dark" ? dark.link : color.peacockDeep }]}>{p.text}</Text>
              </Pressable>
            ))}
          </View>
          <View style={{ flexDirection: "row", gap: 8, alignItems: "center" }}>
            <TextInput testID="chat-text" accessibilityLabel="Write a short message" value={text} maxLength={MAX}
              onChangeText={setText} placeholder="Write a short message" placeholderTextColor={c.muted}
              style={[textFont("600"), s.input, { borderColor: c.line, backgroundColor: c.field, color: c.text }]} />
            <Pressable testID="chat-send" accessibilityRole="button" accessibilityLabel="Send" disabled={busy || !text.trim()}
              onPress={() => void go({ text: text.trim() })} style={[s.send, { opacity: busy || !text.trim() ? 0.5 : 1 }]}>
              <Text style={[textFont("800"), { color: color.white }]}>Send</Text>
            </Pressable>
          </View>
          {error ? <Text style={[textFont("600"), { color: color.chili, marginTop: 8 }]}>{error}</Text> : null}
        </KeyboardAvoidingView>
      </Modal>
    </>
  );
}

const s = StyleSheet.create({
  round: { height: 48, paddingHorizontal: 18, borderRadius: radius.pill, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  badge: {
    position: "absolute", top: -4, right: -4, minWidth: 20, height: 20, borderRadius: 10, paddingHorizontal: 5,
    backgroundColor: color.chili, alignItems: "center", justifyContent: "center",
  },
  scrim: { flex: 1, backgroundColor: "rgba(17, 20, 24, 0.4)" },
  sheet: { padding: 20, paddingBottom: 28, borderTopLeftRadius: 28, borderTopRightRadius: 28, gap: 8 },
  bubble: { maxWidth: "80%", paddingHorizontal: 14, paddingVertical: 10, borderRadius: 18 },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 8, paddingVertical: 4 },
  chip: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: radius.pill },
  input: { flex: 1, height: 48, borderRadius: radius.pill, borderWidth: 1.5, paddingHorizontal: 16, fontSize: 15 },
  send: { height: 48, paddingHorizontal: 20, borderRadius: radius.pill, backgroundColor: color.peacock, alignItems: "center", justifyContent: "center" },
});
