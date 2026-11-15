// Quick messages between the customer and the rider during an active order (B2).
// Preset messages plus a short text, live over the order's tracking socket
// (realtime) with a push when the app is closed. The button only shows while
// the conversation is open (a rider assigned, not yet delivered); nobody sees
// a phone number. Quick messages come from the API in the app's language
// (`lang`); each side reads them in their own (round 5).
import { unwrap, type CoreSchemas } from "@bhojango/api-client";
import { useCallback, useEffect, useRef, useState } from "react";
import { KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { useI18n } from "./i18n";
import { api, wsUrl } from "./session";
import { color, dark, radius } from "./ui/theme";
import { field, type } from "./ui/type";

type Chat = CoreSchemas["QuickMessagesOut"];
type Message = CoreSchemas["QuickMessage"];

const MAX = 140;

async function fetchChat(orderId: string, lang: string): Promise<Chat | null> {
  try {
    return unwrap(await api.core.GET("/api/v1/orders/{order_id}/messages", { params: { path: { order_id: orderId }, query: { lang } } }));
  } catch {
    return null; // not ours, or the network: the button just stays hidden
  }
}

/** The conversation for an order: loads it, follows it live, and sends. */
export function useQuickMessages(orderId: string | undefined) {
  const { language } = useI18n();
  const [chat, setChat] = useState<Chat | null>(null);
  const [unread, setUnread] = useState(0);
  const seen = useRef(new Set<string>());

  const apply = useCallback((c: Chat | null) => {
    if (!c) return;
    c.messages.forEach((m) => seen.current.add(m.id));
    setChat(c);
  }, []);
  const load = useCallback(async () => {
    if (orderId) apply(await fetchChat(orderId, language));
  }, [orderId, language, apply]);

  useEffect(() => {
    if (!orderId) return;
    let live = true;
    fetchChat(orderId, language).then((c) => live && apply(c)).catch(() => undefined);
    const ws = new WebSocket(wsUrl(`/ws/track/${orderId}`));
    ws.onmessage = (e) => {
      const m = JSON.parse(String(e.data)) as {
        type: string; payload: { id: string; sender_role: string; text: string; at: string; preset?: string | null };
      };
      if (m.type === "status_change" || m.type === "rider_assigned") void load();
      if (m.type !== "chat_message" || seen.current.has(m.payload.id)) return;
      seen.current.add(m.payload.id);
      if (m.payload.preset) {
        // A quick message: the API has it in our language (the socket carries the sender's words).
        setChat((c) => {
          if (c && m.payload.sender_role !== c.me) setUnread((n) => n + 1);
          return c;
        });
        void load();
        return;
      }
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
  }, [orderId, language, load, apply]);

  const send = useCallback(async (body: { preset: string } | { text: string }) => {
    if (!orderId) return;
    const m = unwrap(await api.core.POST("/api/v1/orders/{order_id}/messages", {
      params: { path: { order_id: orderId }, query: { lang: language } }, body,
    }));
    if (seen.current.has(m.id)) return;
    seen.current.add(m.id);
    setChat((c) => (c ? { ...c, messages: [...c.messages, m] } : c));
  }, [orderId, language]);

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
  const { t } = useI18n();
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
      setError((e as Error).message || t("track.send_failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {render ? render(open, unread, chat.other_name) : (
        <Pressable testID="chat-open" accessibilityRole="button" onPress={open}
          accessibilityLabel={`${t("app.chat.title", { name: chat.other_name })}${unread ? `, ${t("app.chat.new", { count: unread })}` : ""}`}
          style={[s.round, { borderColor: c.line }]}>
          <Text style={[type.label, { color: c.text }]}>{t("track.message")}</Text>
          {unread ? <View style={s.badge}><Text style={[type.caption, { color: color.white }]}>{unread}</Text></View> : null}
        </Pressable>
      )}
      <Modal transparent visible={visible} animationType="slide" onRequestClose={() => setVisible(false)}>
        <Pressable style={s.scrim} onPress={() => setVisible(false)} accessibilityLabel={t("app.chat.close")} />
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={[s.sheet, { backgroundColor: c.bg }]}>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <View style={{ flex: 1 }}>
              <Text accessibilityRole="header" style={[type.h3, { color: c.text }]}>{t("app.chat.title", { name: chat.other_name })}</Text>
              <Text style={[type.small, { color: c.muted, marginTop: 2 }]}>{t("app.chat.note")}</Text>
            </View>
            <Pressable accessibilityRole="button" onPress={() => setVisible(false)} style={{ padding: 8 }}>
              <Text style={[type.label, { color: c.muted }]}>{t("common.close")}</Text>
            </Pressable>
          </View>
          <ScrollView ref={list as never} style={{ maxHeight: 260 }} contentContainerStyle={{ gap: 8, paddingVertical: 12 }}
            onContentSizeChange={() => list.current?.scrollToEnd({ animated: false })}>
            {chat.messages.length === 0 ? (
              <Text style={[type.small, { color: c.muted }]}>{t("app.chat.empty")}</Text>
            ) : chat.messages.map((m) => (
              <View key={m.id} accessibilityLabel={`${m.mine ? t("track.you_said") : t("track.they_said", { name: chat.other_name })} ${m.text}`}
                style={[s.bubble, m.mine ? { alignSelf: "flex-end", backgroundColor: color.peacock } : { alignSelf: "flex-start", backgroundColor: c.theirs }]}>
                <Text style={[type.label, { color: m.mine ? color.white : c.text }]}>{m.text}</Text>
              </View>
            ))}
          </ScrollView>
          <View style={s.chips}>
            {chat.presets.map((p) => (
              <Pressable key={p.key} accessibilityRole="button" disabled={busy} onPress={() => void go({ preset: p.key })}
                style={[s.chip, { backgroundColor: c.chip }]}>
                <Text style={[type.label, { color: tone === "dark" ? dark.link : color.peacockDeep }]}>{p.text}</Text>
              </Pressable>
            ))}
          </View>
          <View style={{ flexDirection: "row", gap: 8, alignItems: "center" }}>
            <TextInput disableFullscreenUI testID="chat-text" accessibilityLabel={t("track.write")} value={text} maxLength={MAX}
              onChangeText={setText} placeholder={t("track.write")} placeholderTextColor={c.muted}
              style={[field.body, s.input, { borderColor: c.line, backgroundColor: c.field, color: c.text }]} />
            <Pressable testID="chat-send" accessibilityRole="button" accessibilityLabel={t("track.send")} disabled={busy || !text.trim()}
              onPress={() => void go({ text: text.trim() })} style={[s.send, { opacity: busy || !text.trim() ? 0.5 : 1 }]}>
              <Text style={[type.label, { color: color.white }]}>{t("track.send")}</Text>
            </Pressable>
          </View>
          {error ? <Text style={[type.small, { color: color.chili, marginTop: 8 }]}>{error}</Text> : null}
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
  input: { flex: 1, height: 48, borderRadius: radius.pill, borderWidth: 1.5, paddingHorizontal: 16 },
  send: { height: 48, paddingHorizontal: 20, borderRadius: radius.pill, backgroundColor: color.peacock, alignItems: "center", justifyContent: "center" },
});
