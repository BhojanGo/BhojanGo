// PartnerOnboarding.html: the partner application. Steps on the left (and
// your terms), the current step on the right: FSSAI licence, GST and bank,
// menu, then we check everything and switch the kitchen on.
import { api, ApiError, unwrap, useSession } from "@bhojango/mobile-core";
import * as DocumentPicker from "expo-document-picker";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Linking, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useKitchen, useLoad, type Application } from "../lib/data";
import { Btn, color, displayFont, Icon, radius, t, textFont, tone } from "../lib/ui";
import { uploadFile } from "../lib/upload";

type Step = Application["steps"][number];

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "31 Mar 2028" or "2028-03-31" → ISO date. */
function parseDate(v: string): string | null {
  const iso = v.trim().match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) return v.trim();
  const m = v.trim().match(/^(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})$/);
  if (!m) return null;
  const [, day = "", name = "", year = ""] = m;
  const mon = MONTHS.findIndex((x) => x.toLowerCase() === name.toLowerCase());
  return mon < 0 ? null : `${year}-${String(mon + 1).padStart(2, "0")}-${day.padStart(2, "0")}`;
}

function showDate(iso: string | null | undefined) {
  if (!iso) return "";
  const [y = 0, m = 1, d = 1] = iso.split("-").map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

export default function Apply() {
  const kitchen = useKitchen((s) => s.kitchen);
  const signOut = useSession((s) => s.signOut);
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
          <Text accessibilityRole="header" style={t.h1}>Partner application</Text>
          <Text style={t.muted}>{[a?.name ?? kitchen.name, a?.area, kitchen.city].filter(Boolean).join(" · ")}</Text>
        </View>
        <Btn title="Save and exit" onPress={async () => { await signOut(); router.replace("/sign-in"); }} />
      </View>
      <View style={{ flex: 1, flexDirection: "row", padding: 24, gap: 24 }}>
        <View style={{ width: 320, gap: 16 }}>
          <View style={s.panel} accessibilityLabel="Application steps">
            <View style={s.between}>
              <Text style={t.label}>Your progress</Text>
              <Text style={t.muted}>{a ? `${a.done} of ${a.total} done` : ""}</Text>
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
                  <Text style={[textFont(on ? "800" : "600"), { fontSize: 15, color: x.done || on ? color.kohl : color.muted }]}>{x.title}</Text>
                </Pressable>
              );
            })}
          </View>
          {a?.commission_percent ? (
            <View style={[s.panel, { backgroundColor: color.peacockDeep, borderColor: color.peacockDeep }]} accessibilityLabel="Your terms">
              <Text style={[textFont("700"), { fontSize: 13, color: "#CFE3E5" }]}>Your terms</Text>
              <Text style={[displayFont("600"), { fontSize: 40, color: color.white }]}>{Number(a.commission_percent)}%</Text>
              <Text style={[textFont("400"), { fontSize: 14, lineHeight: 20, color: "#CFE3E5" }]}>Commission on food only. Weekly payouts. You set your own prices and offers.</Text>
            </View>
          ) : null}
        </View>
        <ScrollView style={[s.panel, { flex: 1, padding: 0 }]} contentContainerStyle={{ padding: 32, gap: 16 }}>
          {a ? (
            <>
              <Text style={[textFont("700"), { fontSize: 13, color: color.peacock }]}>Step {idx + 1} of {a.total}</Text>
              <StepBody app={a} stepKey={current} onSaved={async () => { const n = await app.reload(); setStep(n?.current ?? null); }} />
            </>
          ) : <Text style={t.muted}>{app.error ?? "Loading…"}</Text>}
        </ScrollView>
      </View>
    </SafeAreaView>
  );
}

function StepBody({ app: a, stepKey, onSaved }: { app: Application; stepKey: string; onSaved: () => Promise<void> }) {
  const step = a.steps.find((x) => x.key === stepKey) as Step;
  if (stepKey === "fssai") return <Fssai app={a} onSaved={onSaved} />;
  if (stepKey === "gst_bank") return <GstBank app={a} onSaved={onSaved} />;
  return (
    <>
      <Text style={t.big}>{step.title}</Text>
      <Text style={t.body}>{step.detail}</Text>
      {stepKey === "menu" ? <Text style={t.muted}>Add dishes, prices and photos with your BhojanGo partner manager; this tablet shows them once you&apos;re live.</Text> : null}
      {stepKey === "go_live" ? <Text style={t.muted}>When every step is done we check your details and switch your kitchen on. This tablet then rings for new orders.</Text> : null}
      <Text style={[textFont("700"), { color: step.done ? color.peacock : tone.kesarInk }]}>{step.done ? "Done" : "Not done yet"}</Text>
    </>
  );
}

function Fssai({ app: a, onSaved }: { app: Application; onSaved: () => Promise<void> }) {
  const kitchen = useKitchen((s) => s.kitchen)!;
  const [num, setNum] = useState(a.fssai_number ? a.fssai_number.replace(/(\d{4})(\d{4})(\d{4})(\d{2})/, "$1 $2 $3 $4") : "");
  const [until, setUntil] = useState(showDate(a.fssai_expires_on));
  const [doc, setDoc] = useState<{ name: string; size: number; key: string | null } | null>(a.fssai_document ? { name: "Licence on file", size: 0, key: null } : null);
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
      const key = await uploadFile(f.uri, f.mimeType ?? "application/pdf", "partner_document");
      setDoc({ name: f.name, size: f.size ?? 0, key });
    } catch (e) {
      setDoc(null);
      setMsg((e as Error).message);
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
      <Text style={t.big}>FSSAI food licence</Text>
      <Text style={t.body}>Every kitchen on BhojanGo shows a valid FSSAI licence on its page.</Text>
      <View style={{ flexDirection: "row", gap: 16 }}>
        <View style={{ flex: 1, gap: 6 }}>
          <Text style={t.label}>Licence number</Text>
          <TextInput testID="fssai-number" accessibilityLabel="Licence number" value={num} keyboardType="number-pad" maxLength={17}
            onChangeText={(v) => setNum(v.replace(/\D/g, "").slice(0, 14).replace(/(\d{4})(?=\d)/g, "$1 "))} style={[textFont("600"), s.input]} />
          <Text style={t.muted}>14 digits, on the top of your certificate</Text>
        </View>
        <View style={{ flex: 1, gap: 6 }}>
          <Text style={t.label}>Valid until</Text>
          <TextInput testID="fssai-until" accessibilityLabel="Valid until" value={until} onChangeText={setUntil} placeholder="31 Mar 2028"
            placeholderTextColor={color.muted} style={[textFont("600"), s.input]} />
          <Text style={t.muted}>We&apos;ll remind you 60 days before it expires</Text>
        </View>
      </View>
      <Text style={t.label}>Licence document</Text>
      {doc ? (
        <View style={s.file}>
          <View style={s.pdf}><Text style={[textFont("800"), { fontSize: 12, color: tone.reject }]}>{doc.name.toLowerCase().endsWith(".pdf") ? "PDF" : "IMG"}</Text></View>
          <View style={{ flex: 1 }}>
            <Text style={[textFont("700"), { fontSize: 15 }]}>{doc.name}</Text>
            <Text style={t.muted}>{doc.size ? `${(doc.size / 1048576).toFixed(1)} MB · ` : ""}{doc.key ? "uploaded just now" : doc.size ? "uploading…" : "on file"}</Text>
          </View>
          <Btn title="Replace" onPress={pick} />
        </View>
      ) : (
        <Pressable accessibilityRole="button" onPress={pick} style={[s.file, { borderStyle: "dashed", justifyContent: "center" }]}>
          <Icon name="doc" stroke={color.peacock} />
          <Text style={[textFont("700"), { color: color.peacock }]}>Upload the licence (PDF or photo)</Text>
        </Pressable>
      )}
      <View style={s.info}>
        <Icon name="info" size={20} stroke={color.peacockDeep} />
        <Text style={[t.body, { flex: 1, fontSize: 14 }]}>We check this licence with FSSAI before your kitchen goes live. If it expires, your listing pauses until you upload the renewal.</Text>
      </View>
      {msg ? <Text style={[textFont("600"), { color: color.chili }]}>{msg}</Text> : null}
      <View style={{ flexDirection: "row", gap: 12, justifyContent: "flex-end" }}>
        <Btn title="Save and continue" kind="primary" height={56} busy={busy} disabled={digits.length !== 14 || !date} onPress={save} />
      </View>
    </>
  );
}

function GstBank({ app: a, onSaved }: { app: Application; onSaved: () => Promise<void> }) {
  const kitchen = useKitchen((s) => s.kitchen)!;
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
      setMsg(e instanceof ApiError ? e.message : "Check the GSTIN: 15 characters, e.g. 36AABCU9603R1ZM");
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
      <Text style={t.big}>GST and bank</Text>
      <Text style={t.body}>Your GSTIN goes on customers&apos; bills; your bank is where your weekly payout lands.</Text>
      <Text style={t.label}>GSTIN</Text>
      <View style={{ flexDirection: "row", gap: 12 }}>
        <TextInput testID="gstin" accessibilityLabel="GSTIN" value={gstin} onChangeText={(v) => setGstin(v.toUpperCase())} autoCapitalize="characters" maxLength={15}
          placeholder="36AABCU9603R1ZM" placeholderTextColor={color.muted} style={[textFont("600"), s.input, { flex: 1 }]} />
        <Btn title={a.gstin ? "Update" : "Save GSTIN"} height={56} busy={busy} disabled={gstin.length !== 15} onPress={saveGst} />
      </View>
      <Text style={t.label}>Bank account</Text>
      <View style={s.file}>
        <View style={{ flex: 1 }}>
          <Text style={[textFont("700"), { fontSize: 15 }]}>{a.payout_account === "active" ? "Bank account confirmed" : a.payout_account ? "Waiting for your bank details" : "No bank account yet"}</Text>
          <Text style={t.muted}>Set up securely with our payments partner (Razorpay Route in India).</Text>
        </View>
        {a.payout_account !== "active" ? <Btn title={a.payout_account ? "Continue" : "Add bank account"} kind="primary" onPress={bank} /> : null}
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
