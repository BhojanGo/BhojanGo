// Quick messages between the customer and the rider during an active order (B2).
// Preset messages plus a short text, live over the order's tracking socket
// (realtime) with a push when the app is closed. The button only shows while
// the conversation is open (a rider assigned, not yet delivered); nobody sees
// a phone number. Quick messages come from the API in the app's language
// (`lang`); each side reads them in their own (round 5).
//
// Report and block (R19, Apple 1.2): press and hold the other person's message (or
// "Report" under their latest one) to report it to BhojanGo with a reason and an
// optional note, and maybe block them too; "Block" in the header stops their
// messages reaching this person (per pair of people, until unblocked).
import { unwrap, type CoreSchemas } from "@bhojango/api-client";
import { useCallback, useEffect, useRef, useState } from "react";
import { KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native";

import { mergeChat } from "./chatMerge";
import { useI18n } from "./i18n";
import { api, liveSocket } from "./session";
import { color, dark, radius } from "./ui/theme";
import { field, type } from "./ui/type";

type Chat = CoreSchemas["QuickMessagesOut"];
type Message = CoreSchemas["QuickMessage"];

const MAX = 140;
export const REPORT_REASONS = ["abusive", "harassment", "spam", "unsafe", "other"] as const;
export type ReportReason = (typeof REPORT_REASONS)[number];

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

  // What the socket handler needs without re-subscribing: am I customer or rider, did I block them.
  const blockedRef = useRef(false);
  const meRef = useRef<string | null>(null);
  const apply = useCallback((c: Chat | null) => {
    if (!c) return;
    c.messages.forEach((m) => seen.current.add(m.id));
    blockedRef.current = !!c.blocked;
    meRef.current = c.me;
    // R35: merged, never replaced: a fetch that started before a send must not drop it
    setChat((prev) => mergeChat(c, prev));
  }, []);
  // Fetches can finish out of order (a poll, a status change, a quick message): only
  // the newest one applies, so an older list never replaces a newer one.
  const latest = useRef(0);
  const load = useCallback(async () => {
    if (!orderId) return;
    const n = ++latest.current;
    const c = await fetchChat(orderId, language);
    if (n === latest.current) apply(c);
  }, [orderId, language, apply]);

  useEffect(() => {
    if (!orderId) return;
    load().catch(() => undefined);
    const stopSocket = liveSocket(`/ws/track/${orderId}`, (e) => {
      const m = JSON.parse(String(e.data)) as {
        type: string; payload: { id: string; sender_role: string; text: string; at: string; preset?: string | null };
      };
      if (m.type === "status_change" || m.type === "rider_assigned") void load();
      if (m.type !== "chat_message" || seen.current.has(m.payload.id)) return;
      seen.current.add(m.payload.id);
      if (blockedRef.current && m.payload.sender_role !== meRef.current) return; // R19: I blocked them
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
    });
    const poll = setInterval(() => void load(), 30000); // the socket can drop on mobile networks
    return () => {
      latest.current++; // a fetch still in flight no longer applies
      clearInterval(poll);
      stopSocket();
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

  /** Report one of the other person's messages (R19); `block` also blocks them. */
  const report = useCallback(async (messageId: string, body: { reason: ReportReason; note?: string | null; block?: boolean }) => {
    if (!orderId) return;
    unwrap(await api.core.POST("/api/v1/orders/{order_id}/messages/{message_id}/report", {
      params: { path: { order_id: orderId, message_id: messageId } }, body,
    }));
    if (body.block) await load();
  }, [orderId, load]);

  /** Block or unblock the other person on this order (R19). */
  const setBlocked = useCallback(async (block: boolean) => {
    if (!orderId) return;
    const path = { params: { path: { order_id: orderId } } };
    unwrap(block ? await api.core.POST("/api/v1/orders/{order_id}/messages/block", path)
      : await api.core.DELETE("/api/v1/orders/{order_id}/messages/block", path));
    await load();
  }, [orderId, load]);

  return { chat, unread, markRead: () => setUnread(0), send, report, setBlocked, reload: load };
}

/** A button that opens the conversation; renders nothing while it's closed. */
export function QuickChat({ orderId, tone = "light", render }: {
  orderId: string | undefined;
  tone?: "light" | "dark";
  /** Draw the button yourself: called with what opens the chat and the unread count. */
  render?: (open: () => void, unread: number, name: string) => React.ReactNode;
}) {
  const { chat, unread, markRead, send, report, setBlocked } = useQuickMessages(orderId);
  const { t } = useI18n();
  const [visible, setVisible] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const list = useRef<{ scrollToEnd: (o?: { animated?: boolean }) => void } | null>(null);
  // R19: the report view (which message, why, a note, also block) and the block confirmation.
  const [view, setView] = useState<"chat" | "report" | "done" | "block">("chat");
  const [reporting, setReporting] = useState<Message | null>(null);
  const [reason, setReason] = useState<ReportReason | null>(null);
  const [note, setNote] = useState("");
  const [alsoBlock, setAlsoBlock] = useState(false);
  if (!chat?.open) return null;
  const c = tone === "dark"
    ? { bg: dark.surface, text: dark.text, muted: dark.muted, line: dark.lineStrong, field: dark.ground, theirs: dark.raised, chip: dark.raised }
    : { bg: color.white, text: color.kohl, muted: color.muted, line: color.lineStrong, field: color.white, theirs: color.porcelain, chip: color.peacockMist };
  const open = () => {
    markRead();
    setView("chat");
    setVisible(true);
  };
  const close = () => {
    setVisible(false);
    setView("chat");
    setError(null);
  };
  const startReport = (m: Message) => {
    setReporting(m);
    setReason(null);
    setNote("");
    setAlsoBlock(false);
    setError(null);
    setView("report");
  };
  async function sendReport() {
    if (!reporting || !reason) return;
    setBusy(true);
    setError(null);
    try {
      await report(reporting.id, { reason, note: note.trim() || null, block: alsoBlock });
      setView("done");
    } catch {
      setError(t("app.chat.report_failed"));
    } finally {
      setBusy(false);
    }
  }
  async function changeBlock(block: boolean) {
    setBusy(true);
    setError(null);
    try {
      await setBlocked(block);
      setView("chat");
    } catch {
      setError(t("app.chat.block_failed"));
    } finally {
      setBusy(false);
    }
  }
  const name = chat.other_name;
  const lastTheirs = [...chat.messages].reverse().find((m) => !m.mine)?.id;
  const accent = tone === "dark" ? dark.link : color.peacockDeep;
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
      <Modal transparent visible={visible} animationType="slide" onRequestClose={close}>
        <Pressable style={s.scrim} onPress={close} accessibilityLabel={t("app.chat.close")} />
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={[s.sheet, { backgroundColor: c.bg }]}>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <View style={{ flex: 1 }}>
              <Text accessibilityRole="header" style={[type.h3, { color: c.text }]}>{t("app.chat.title", { name: chat.other_name })}</Text>
              <Text style={[type.small, { color: c.muted, marginTop: 2 }]}>{t("app.chat.note")}</Text>
            </View>
            {view === "chat" ? (
              chat.blocked ? (
                <Pressable testID="chat-unblock" accessibilityRole="button" disabled={busy} onPress={() => void changeBlock(false)} style={{ padding: 8 }}>
                  <Text style={[type.label, { color: accent }]}>{t("app.chat.unblock")}</Text>
                </Pressable>
              ) : (
                <Pressable testID="chat-block" accessibilityRole="button" onPress={() => { setError(null); setView("block"); }} style={{ padding: 8 }}>
                  <Text style={[type.label, { color: c.muted }]}>{t("app.chat.block")}</Text>
                </Pressable>
              )
            ) : null}
            <Pressable accessibilityRole="button" onPress={close} style={{ padding: 8 }}>
              <Text style={[type.label, { color: c.muted }]}>{t("common.close")}</Text>
            </Pressable>
          </View>
          {view === "report" && reporting ? (
            <View testID="report-sheet" style={{ gap: 10, paddingTop: 8 }}>
              <Text accessibilityRole="header" style={[type.label, { color: c.text }]}>{t("app.chat.report_title")}</Text>
              <View style={[s.quote, { borderColor: c.line }]}><Text style={[type.small, { color: c.text }]}>{reporting.text}</Text></View>
              <Text style={[type.small, { color: c.muted }]}>{t("app.chat.report_intro")}</Text>
              <View accessibilityRole="radiogroup" style={s.chips}>
                {REPORT_REASONS.map((r) => (
                  <Pressable key={r} testID={`report-reason-${r}`} accessibilityRole="radio" accessibilityState={{ checked: reason === r }}
                    onPress={() => setReason(r)}
                    style={[s.chip, { backgroundColor: c.chip, borderWidth: 1.5, borderColor: reason === r ? color.peacock : "transparent" }]}>
                    <Text style={[type.label, { color: reason === r ? accent : c.text }]}>{t(`app.chat.reason_${r}`)}</Text>
                  </Pressable>
                ))}
              </View>
              <TextInput disableFullscreenUI testID="report-note" accessibilityLabel={t("app.chat.report_note")} value={note} maxLength={300}
                onChangeText={setNote} placeholder={t("app.chat.report_note")} placeholderTextColor={c.muted}
                style={[field.body, s.input, { flex: 0, borderColor: c.line, backgroundColor: c.field, color: c.text }]} />
              <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
                <Text style={[type.label, { color: c.text, flex: 1 }]}>{t("app.chat.also_block", { name })}</Text>
                <Switch testID="report-also-block" accessibilityLabel={t("app.chat.also_block", { name })} value={alsoBlock}
                  onValueChange={setAlsoBlock} trackColor={{ true: color.peacock }} />
              </View>
              <View style={{ flexDirection: "row", gap: 8 }}>
                <Pressable accessibilityRole="button" onPress={() => setView("chat")} style={[s.ghost, { borderColor: c.line }]}>
                  <Text style={[type.label, { color: c.text }]}>{t("app.chat.cancel")}</Text>
                </Pressable>
                <Pressable testID="report-send" accessibilityRole="button" disabled={busy || !reason} onPress={() => void sendReport()}
                  style={[s.send, { flex: 1, opacity: busy || !reason ? 0.5 : 1 }]}>
                  <Text style={[type.label, { color: color.white }]}>{busy ? t("app.chat.sending") : t("app.chat.send_report")}</Text>
                </Pressable>
              </View>
            </View>
          ) : view === "done" ? (
            <View testID="report-done" style={{ gap: 8, paddingVertical: 12 }}>
              <Text accessibilityRole="header" style={[type.label, { color: c.text }]}>{t("app.chat.report_sent")}</Text>
              <Text style={[type.small, { color: c.muted }]}>{t("app.chat.report_sent_body")}</Text>
              {chat.blocked ? <Text style={[type.small, { color: c.muted }]}>{t("app.chat.blocked_note", { name })}</Text> : null}
              <Pressable accessibilityRole="button" onPress={() => setView("chat")} style={[s.ghost, { borderColor: c.line, alignSelf: "flex-start" }]}>
                <Text style={[type.label, { color: c.text }]}>{t("common.close")}</Text>
              </Pressable>
            </View>
          ) : view === "block" ? (
            <View style={{ gap: 10, paddingVertical: 12 }}>
              <Text accessibilityRole="header" style={[type.label, { color: c.text }]}>{t("app.chat.block_title", { name })}</Text>
              <Text style={[type.small, { color: c.muted }]}>{t("app.chat.block_body", { name })}</Text>
              <View style={{ flexDirection: "row", gap: 8 }}>
                <Pressable accessibilityRole="button" onPress={() => setView("chat")} style={[s.ghost, { borderColor: c.line }]}>
                  <Text style={[type.label, { color: c.text }]}>{t("app.chat.cancel")}</Text>
                </Pressable>
                <Pressable testID="chat-block-confirm" accessibilityRole="button" disabled={busy} onPress={() => void changeBlock(true)}
                  style={[s.send, { flex: 1, backgroundColor: color.chili, opacity: busy ? 0.5 : 1 }]}>
                  <Text style={[type.label, { color: color.white }]}>{t("app.chat.block_confirm")}</Text>
                </Pressable>
              </View>
            </View>
          ) : (
          <>
          {chat.blocked ? <Text testID="chat-blocked-note" style={[type.small, { color: c.muted }]}>{t("app.chat.blocked_note", { name })}</Text> : null}
          <ScrollView ref={list as never} style={{ maxHeight: 260 }} contentContainerStyle={{ gap: 8, paddingVertical: 12 }}
            onContentSizeChange={() => list.current?.scrollToEnd({ animated: false })}>
            {chat.messages.length === 0 ? (
              <Text style={[type.small, { color: c.muted }]}>{t("app.chat.empty")}</Text>
            ) : chat.messages.map((m) => m.mine ? (
              <View key={m.id} accessibilityLabel={`${t("track.you_said")} ${m.text}`}
                style={[s.bubble, { alignSelf: "flex-end", backgroundColor: color.peacock }]}>
                <Text style={[type.label, { color: color.white }]}>{m.text}</Text>
              </View>
            ) : (
              <View key={m.id} style={{ alignSelf: "flex-start", maxWidth: "80%", gap: 2 }}>
                <Pressable testID="chat-msg-theirs" onLongPress={() => startReport(m)} delayLongPress={350}
                  accessibilityLabel={`${t("track.they_said", { name })} ${m.text}`} accessibilityHint={t("app.chat.report_hint")}
                  accessibilityActions={[{ name: "report", label: t("app.chat.report") }]}
                  onAccessibilityAction={(e) => e.nativeEvent.actionName === "report" && startReport(m)}
                  style={[s.bubble, { maxWidth: "100%", backgroundColor: c.theirs }]}>
                  <Text style={[type.label, { color: c.text }]}>{m.text}</Text>
                </Pressable>
                {m.id === lastTheirs ? (
                  <Pressable testID="chat-report-link" accessibilityRole="button" accessibilityLabel={t("app.chat.report_title")}
                    onPress={() => startReport(m)} hitSlop={8} style={{ paddingHorizontal: 6 }}>
                    <Text style={[type.caption, { color: c.muted, textDecorationLine: "underline" }]}>{t("app.chat.report")}</Text>
                  </Pressable>
                ) : null}
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
          </>
          )}
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
  ghost: { height: 48, paddingHorizontal: 20, borderRadius: radius.pill, borderWidth: 1, alignItems: "center", justifyContent: "center" },
  quote: { borderLeftWidth: 3, paddingLeft: 10, paddingVertical: 4 },
});
