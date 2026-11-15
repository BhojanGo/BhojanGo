// Upload a licence or insurance photo for review (from the onboarding checklist).
import { api, ApiError, unwrap, useI18n } from "@bhojango/mobile-core";
import * as ImagePicker from "expo-image-picker";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Image, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../lib/icons";
import { night, radius, space, textFont, ui } from "../lib/theme";
import { uploadFile } from "../lib/upload";


export default function Document() {
  const { kind } = useLocalSearchParams<{ kind: "licence" | "insurance" }>();
  const { t } = useI18n();
  const known = kind === "licence" || kind === "insurance";
  const [picked, setPicked] = useState<{ uri: string; mime: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function choose(from: "camera" | "library") {
    setMsg(null);
    const perm = from === "camera" ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      setMsg(from === "camera" ? t("rider.document.camera_needed") : t("rider.document.photos_needed"));
      return;
    }
    const r = from === "camera"
      ? await ImagePicker.launchCameraAsync({ quality: 0.7 })
      : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.7 });
    if (!r.canceled && r.assets[0]) setPicked({ uri: r.assets[0].uri, mime: r.assets[0].mimeType ?? "image/jpeg" });
  }

  async function send() {
    if (!picked) return;
    setBusy(true);
    setMsg(null);
    try {
      const key = await uploadFile(picked.uri, picked.mime, "rider_document");
      unwrap(await api.core.POST("/api/v1/riders/me/documents", { body: { kind, file_key: key } }));
      router.back();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : (e as Error).message || t("rider.upload.failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView testID="document-screen" style={[ui.screen, { padding: space[5], gap: space[4] }]}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <Text accessibilityRole="header" style={[ui.h1, { fontSize: 28, flex: 1 }]}>{known ? t(`rider.checklist.steps.${kind}`) : t("rider.document.title")}</Text>
        <Pressable accessibilityRole="button" accessibilityLabel={t("common.close")} onPress={() => router.back()} style={styles.close}><Icon name="close" /></Pressable>
      </View>
      <Text style={[ui.body, { color: night.muted }]}>{known ? t(`rider.document.hint_${kind}`) : t("rider.document.hint")}</Text>
      <View style={styles.preview}>
        {picked ? <Image source={{ uri: picked.uri }} style={StyleSheet.absoluteFill} resizeMode="contain" accessibilityLabel={t("rider.document.your_photo")} /> : (
          <>
            <Icon name="document" size={32} stroke={night.link} />
            <Text style={ui.muted}>{t("rider.document.no_photo")}</Text>
          </>
        )}
      </View>
      <View style={{ flexDirection: "row", gap: 10 }}>
        <Pressable accessibilityRole="button" onPress={() => choose("camera")} style={[ui.outline, { flex: 1 }]}>
          <Icon name="camera" size={20} stroke={night.link} />
          <Text style={[ui.bold, textFont("700")]}>{t("rider.document.take")}</Text>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={() => choose("library")} style={[ui.outline, { flex: 1 }]}>
          <Text style={[ui.bold, textFont("700")]}>{t("rider.document.choose")}</Text>
        </Pressable>
      </View>
      {msg ? <Text style={[textFont("600"), { color: night.sosText }]}>{msg}</Text> : null}
      <View style={{ flex: 1 }} />
      <Text style={ui.muted}>{t("rider.document.private")}</Text>
      <Pressable accessibilityRole="button" disabled={!picked || busy} onPress={send} style={[ui.cta, { opacity: picked && !busy ? 1 : 0.5 }]}>
        {busy ? <ActivityIndicator color={night.onKesar} /> : null}
        <Text style={ui.ctaText}>{busy ? t("rider.document.sending") : t("rider.document.send")}</Text>
      </Pressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  close: { width: 44, height: 44, alignItems: "center", justifyContent: "center" },
  preview: {
    height: 220, borderRadius: radius.card, borderWidth: 1.5, borderStyle: "dashed", borderColor: night.dashed, backgroundColor: night.map,
    alignItems: "center", justifyContent: "center", gap: 8, overflow: "hidden",
  },
});
