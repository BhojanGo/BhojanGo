// PartnerOnboarding.html: the partner application. Steps on the left (and
// your terms), the current step on the right: FSSAI licence, GST and bank,
// menu, then we check everything and switch the kitchen on.
import { api, ApiError, unwrap, useCountry, useI18n, useSession, type Translate } from "@bhojango/mobile-core";
import * as DocumentPicker from "expo-document-picker";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, Text, TextInput, useWindowDimensions, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useKitchen, useLoad, type Application } from "../lib/data";
import { Btn, color, displayFont, Icon, radius, t, textFont, tone } from "../lib/ui";
import { uploadFile } from "../lib/upload";

type Step = Application["steps"][number];

// data-ok: English month abbreviations the licence date may be typed with ("31 Mar 2028"), besides 2028-03-31 and 31/03/2028.
const MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];

/** "31 Mar 2028", "31/03/2028" or "2028-03-31" → ISO date (day first, as on the certificate). */
function parseDate(v: string): string | null {
  const s = v.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const num = s.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/);
  if (num) {
    const [, day = "", mon = "", year = ""] = num;
    return Number(mon) >= 1 && Number(mon) <= 12 ? `${year}-${mon.padStart(2, "0")}-${day.padStart(2, "0")}` : null;
  }
  const m = s.match(/^(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})$/);
  if (!m) return null;
  const [, day = "", name = "", year = ""] = m;
  const mon = MONTHS.indexOf(name.toLowerCase());
  return mon < 0 ? null : `${year}-${String(mon + 1).padStart(2, "0")}-${day.padStart(2, "0")}`;
}

/** An ISO date as the field shows it: 31/03/2028 (parseDate reads it back). */
function showDate(iso: string | null | undefined) {
  if (!iso) return "";
  const [y = "", m = "", d = ""] = iso.split("-");
  return `${d}/${m}/${y}`;
}

/**
 * A step's name and detail in the partner's language, from its key and status (the
 * API's words for a step the app doesn't know). Where the country's tax regime is GST
 * (Markets tax_regime) the licence and tax steps are the FSSAI licence and GST.
 */
function stepText(t: Translate, x: { key: string; title: string; detail: string; done: boolean }, gst: boolean) {
  const v = gst ? "gst" : "other";
  switch (x.key) {
    case "business":
      return { title: t("partner.apply.steps.business"), detail: t("partner.apply.steps.business_detail") };
    case "fssai":
      return { title: t(`partner.apply.steps.fssai_${v}`), detail: t(`partner.apply.steps.fssai_${v}_detail`) };
    case "gst_bank":
      return { title: t(`partner.apply.steps.tax_${v}`), detail: t(`partner.apply.steps.tax_${v}_detail`) };
    case "menu": {
      const n = /^(\d+)/.exec(x.detail)?.[1];
      return { title: t("partner.apply.steps.menu"), detail: n != null ? t("partner.apply.steps.menu_detail", { count: Number(n) }) : x.detail };
    }
    case "go_live":
      return { title: t("partner.apply.steps.go_live"), detail: x.done ? t("partner.apply.steps.go_live_done") : t("partner.apply.steps.go_live_detail") };
    default:
      return { title: x.title, detail: x.detail };
  }
}

export default function Apply() {
  const kitchen = useKitchen((s) => s.kitchen);
  const signOut = useSession((s) => s.signOut);
  const { t: tr } = useI18n();
  const { width } = useWindowDimensions();
  const narrow = width < 1000;
  const gst = useCountry().country?.tax_regime === "gst"; // the kitchen's country (the account's: useKnownCountry)
  const id = kitchen?.id ?? "";
  const app = useLoad(async () => unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/application", { params: { path: { restaurant_id: id } } })), id);
  const [step, setStep] = useState<string | null>(null);
  const a = app.data;
  useEffect(() => {
    if (a?.status === "active") router.replace("/orders");
  }, [a?.status]);
  if (!kitchen) return null;
  const current = step ?? a?.current ?? "fssai";
  const idx = a ? a.steps.findIndex((x) => x.key === current) : 1;

  return (
    <SafeAreaView edges={["left", "right", "top"]} style={{ flex: 1, backgroundColor: color.porcelain }}>
      <View style={s.header}>
        <View style={{ flex: 1 }}>
          <Text accessibilityRole="header" style={t.h1}>{tr("partner.apply.title")}</Text>
          <Text style={t.muted}>{[a?.name ?? kitchen.name, a?.area, kitchen.city].filter(Boolean).join(" · ")}</Text>
        </View>
        <Btn title={tr("partner.apply.save_exit")} onPress={async () => { await signOut(); router.replace("/sign-in"); }} />
      </View>
      <View style={{ flex: 1, flexDirection: "row", padding: narrow ? 16 : 24, gap: narrow ? 16 : 24 }}>
        <ScrollView style={{ width: narrow ? 240 : 320, flexGrow: 0 }} contentContainerStyle={{ gap: 16 }}>
          <View style={s.panel} accessibilityLabel={tr("partner.apply.steps_label")}>
            <View style={s.between}>
              <Text style={t.label}>{tr("partner.apply.progress")}</Text>
              <Text style={t.muted}>{a ? tr("partner.apply.done_of", { done: a.done, total: a.total }) : ""}</Text>
            </View>
            {(a?.steps ?? []).map((x, i) => {
              const on = x.key === current;
              return (
                <Pressable key={x.key} accessibilityRole="button" accessibilityState={{ selected: on }} onPress={() => setStep(x.key)}
                  style={[s.step, on && { backgroundColor: color.peacockMist }]}>
                  {x.done ? (
                    <View style={[s.num, { backgroundColor: color.peacock, borderColor: color.peacock }]}><Icon name="check" size={14} stroke={color.white} width={3} /></View>
                  ) : (
                    <View style={[s.num, on && { borderColor: color.peacock }]}><Text style={[textFont("800"), { fontSize: 13, color: on ? color.peacock : color.muted }]}>{i + 1}</Text></View>
                  )}
                  <Text style={[textFont(on ? "800" : "600"), { fontSize: 15, color: x.done || on ? color.kohl : color.muted, flexShrink: 1 }]}>{stepText(tr, x, gst).title}</Text>
                </Pressable>
              );
            })}
          </View>
          {a?.commission_percent ? (
            <View style={[s.panel, { backgroundColor: color.peacockDeep, borderColor: color.peacockDeep }]} accessibilityLabel={tr("partner.apply.terms")}>
              <Text style={[textFont("700"), { fontSize: 13, color: "#CFE3E5" }]}>{tr("partner.apply.terms")}</Text>
              <Text style={[displayFont("600"), { fontSize: 40, color: color.white }]}>{Number(a.commission_percent)}%</Text>
              <Text style={[textFont("400"), { fontSize: 14, lineHeight: 20, color: "#CFE3E5" }]}>{tr("partner.apply.terms_body")}</Text>
            </View>
          ) : null}
        </ScrollView>
        <ScrollView style={[s.panel, { flex: 1, padding: 0 }]} contentContainerStyle={{ padding: narrow ? 20 : 32, gap: 16 }}>
          {a ? (
            <>
              <Text style={[textFont("700"), { fontSize: 13, color: color.peacock }]}>{tr("partner.apply.step_of", { n: idx + 1, total: a.total })}</Text>
              <StepBody app={a} stepKey={current} onSaved={async () => { const n = await app.reload(); setStep(n?.current ?? null); }} />
            </>
          ) : <Text style={t.muted}>{app.error ?? tr("common.loading")}</Text>}
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

function StepBody({ app: a, stepKey, onSaved }: { app: Application; stepKey: string; onSaved: () => Promise<void> }) {
  const { t: tr } = useI18n();
  const gst = useCountry().country?.tax_regime === "gst";
  const step = a.steps.find((x) => x.key === stepKey) as Step | undefined;
  if (!step) return null;
  const text = stepText(tr, step, gst);
  if (stepKey === "fssai") return <Fssai app={a} onSaved={onSaved} />;
  if (stepKey === "gst_bank") return <GstBank app={a} onSaved={onSaved} />;
  return (
    <>
      <Text style={t.big}>{text.title}</Text>
      <Text style={t.body}>{text.detail}</Text>
      {stepKey === "menu" ? <Text style={t.muted}>{tr("partner.apply.menu_note")}</Text> : null}
      {stepKey === "go_live" ? <Text style={t.muted}>{tr("partner.apply.go_live_note")}</Text> : null}
      <Text style={[textFont("700"), { color: step.done ? color.peacock : tone.kesarInk }]}>{step.done ? tr("partner.apply.done") : tr("partner.apply.not_done")}</Text>
    </>
  );
}

function Fssai({ app: a, onSaved }: { app: Application; onSaved: () => Promise<void> }) {
  const kitchen = useKitchen((s) => s.kitchen)!;
  const { t: tr } = useI18n();
  const [num, setNum] = useState(a.fssai_number ? a.fssai_number.replace(/(\d{4})(\d{4})(\d{4})(\d{2})/, "$1 $2 $3 $4") : "");
  const [until, setUntil] = useState(showDate(a.fssai_expires_on));
  const [doc, setDoc] = useState<{ name: string; size: number; key: string | null } | null>(a.fssai_document ? { name: tr("partner.apply.licence_on_file"), size: 0, key: null } : null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const digits = num.replace(/\D/g, "");
  const date = parseDate(until);

  async function pick() {
    setMsg(null);
    const r = await DocumentPicker.getDocumentAsync({ type: ["application/pdf", "image/jpeg", "image/png"], copyToCacheDirectory: true });
    if (r.canceled || !r.assets[0]) return;
    const f = r.assets[0];
    setDoc({ name: f.name, size: f.size ?? 0, key: null });
    try {
      const { key } = await uploadFile(f.uri, f.mimeType ?? "application/pdf", "partner_document");
      setDoc({ name: f.name, size: f.size ?? 0, key });
    } catch (e) {
      setDoc(null);
      setMsg((e as Error).message || tr("partner.upload.failed"));
    }
  }

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/licence", {
        params: { path: { restaurant_id: kitchen.id } },
        body: { fssai_number: digits, fssai_expires_on: date!, ...(doc?.key ? { document_key: doc.key } : {}) },
      }));
      await onSaved();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Text style={t.big}>{tr("partner.apply.fssai_title")}</Text>
      <Text style={t.body}>{tr("partner.apply.fssai_sub")}</Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 16 }}>
        <View style={{ flex: 1, minWidth: 220, gap: 6 }}>
          <Text style={t.label}>{tr("partner.apply.licence_number")}</Text>
          <TextInput disableFullscreenUI testID="fssai-number" accessibilityLabel={tr("partner.apply.licence_number")} value={num} keyboardType="number-pad" maxLength={17}
            onChangeText={(v) => setNum(v.replace(/\D/g, "").slice(0, 14).replace(/(\d{4})(?=\d)/g, "$1 "))} style={[textFont("600"), s.input]} />
          <Text style={t.muted}>{tr("partner.apply.licence_number_hint")}</Text>
        </View>
        <View style={{ flex: 1, minWidth: 220, gap: 6 }}>
          <Text style={t.label}>{tr("partner.apply.valid_until")}</Text>
          <TextInput disableFullscreenUI testID="fssai-until" accessibilityLabel={tr("partner.apply.valid_until")} value={until} onChangeText={setUntil} placeholder={tr("partner.apply.date_hint")}
            placeholderTextColor={color.muted} style={[textFont("600"), s.input]} />
          <Text style={t.muted}>{tr("partner.apply.remind")}</Text>
        </View>
      </View>
      <Text style={t.label}>{tr("partner.apply.licence_document")}</Text>
      {doc ? (
        <View style={s.file}>
          <View style={s.pdf}><Text style={[textFont("800"), { fontSize: 12, color: tone.reject }]}>{doc.name.toLowerCase().endsWith(".pdf") ? tr("partner.apply.pdf") : tr("partner.apply.img")}</Text></View>
          <View style={{ flex: 1 }}>
            <Text style={[textFont("700"), { fontSize: 15 }]}>{doc.name}</Text>
            <Text style={t.muted}>
              {[doc.size ? tr("partner.apply.megabytes", { size: (doc.size / 1048576).toFixed(1) }) : null,
                doc.key ? tr("partner.apply.uploaded_now") : doc.size ? tr("partner.apply.uploading") : tr("partner.apply.on_file")].filter(Boolean).join(" · ")}
            </Text>
          </View>
          <Btn title={tr("partner.apply.replace")} onPress={pick} />
        </View>
      ) : (
        <Pressable accessibilityRole="button" onPress={pick} style={[s.file, { borderStyle: "dashed", justifyContent: "center" }]}>
          <Icon name="doc" stroke={color.peacock} />
          <Text style={[textFont("700"), { color: color.peacock }]}>{tr("partner.apply.upload_licence")}</Text>
        </Pressable>
      )}
      <View style={s.info}>
        <Icon name="info" size={20} stroke={color.peacockDeep} />
        <Text style={[t.body, { flex: 1, fontSize: 14 }]}>{tr("partner.apply.fssai_check")}</Text>
      </View>
      {msg ? <Text style={[textFont("600"), { color: color.chili }]}>{msg}</Text> : null}
      <View style={{ flexDirection: "row", gap: 12, justifyContent: "flex-end" }}>
        <Btn testID="fssai-save" title={tr("partner.apply.save_continue")} kind="primary" height={56} busy={busy} disabled={digits.length !== 14 || !date} onPress={save} />
      </View>
    </>
  );
}

function GstBank({ app: a, onSaved }: { app: Application; onSaved: () => Promise<void> }) {
  const kitchen = useKitchen((s) => s.kitchen)!;
  const { t: tr } = useI18n();
  const [gstin, setGstin] = useState(a.gstin ?? "");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  async function saveGst() {
    setBusy(true);
    setMsg(null);
    try {
      unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/gst", { params: { path: { restaurant_id: kitchen.id } }, body: { gstin: gstin.toUpperCase() } }));
      await onSaved();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : tr("partner.apply.gstin_check"));
    } finally {
      setBusy(false);
    }
  }
  async function bank() {
    setMsg(null);
    try {
      const r = unwrap(await api.core.POST("/api/v1/finance/payout-accounts", { body: { payee_type: "restaurant", restaurant_id: kitchen.id } })) as { onboarding_url?: string | null };
      if (r.onboarding_url) await Linking.openURL(r.onboarding_url);
      await onSaved();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : (e as Error).message);
    }
  }
  return (
    <>
      <Text style={t.big}>{tr("partner.apply.gst_title")}</Text>
      <Text style={t.body}>{tr("partner.apply.gst_sub")}</Text>
      <Text style={t.label}>{tr("partner.apply.gstin")}</Text>
      <View style={{ flexDirection: "row", gap: 12 }}>
        <TextInput disableFullscreenUI testID="gstin" accessibilityLabel={tr("partner.apply.gstin")} value={gstin} onChangeText={(v) => setGstin(v.toUpperCase())} autoCapitalize="characters" maxLength={15}
          placeholder="36AABCU9603R1ZM" placeholderTextColor={color.muted} style={[textFont("600"), s.input, { flex: 1 }]} />
        <Btn title={a.gstin ? tr("partner.apply.update") : tr("partner.apply.save_gstin")} height={56} busy={busy} disabled={gstin.length !== 15} onPress={saveGst} />
      </View>
      <Text style={t.label}>{tr("partner.apply.bank")}</Text>
      <View style={s.file}>
        <View style={{ flex: 1 }}>
          <Text style={[textFont("700"), { fontSize: 15 }]}>
            {a.payout_account === "active" ? tr("partner.apply.bank_confirmed") : a.payout_account ? tr("partner.apply.bank_waiting") : tr("partner.apply.bank_none")}
          </Text>
          <Text style={t.muted}>{tr("partner.apply.bank_partner")}</Text>
        </View>
        {a.payout_account !== "active" ? <Btn title={a.payout_account ? tr("partner.apply.continue") : tr("partner.apply.add_bank")} kind="primary" onPress={bank} /> : null}
      </View>
      {msg ? <Text style={[textFont("600"), { color: color.chili }]}>{msg}</Text> : null}
    </>
  );
}

const s = StyleSheet.create({
  header: { height: 80, paddingHorizontal: 24, backgroundColor: color.white, borderBottomWidth: 1, borderBottomColor: color.line, flexDirection: "row", alignItems: "center", gap: 16 },
  panel: { backgroundColor: color.white, borderRadius: radius.card, borderWidth: 1, borderColor: color.line, padding: 20, gap: 8 },
  between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 4 },
  step: { flexDirection: "row", alignItems: "center", gap: 12, height: 52, paddingHorizontal: 12, borderRadius: 12 },
  num: { width: 28, height: 28, borderRadius: 14, borderWidth: 2, borderColor: color.lineStrong, alignItems: "center", justifyContent: "center" },
  input: { height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: 16, fontSize: 17 },
  file: { flexDirection: "row", alignItems: "center", gap: 12, padding: 16, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.line },
  pdf: { width: 44, height: 52, borderRadius: 8, backgroundColor: "#FBEAE8", alignItems: "center", justifyContent: "center" },
  info: { flexDirection: "row", gap: 12, padding: 16, borderRadius: radius.card, backgroundColor: color.peacockMist },
});
