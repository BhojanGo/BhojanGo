// RiderOnboarding.html: "Almost ready to ride", five steps, one action.
// The API sends each step's key and status; the words are the app's (rider.checklist.*,
// in the rider's language). A reviewer's note on a rejected document is shown as written.
import { SafeAreaView, type Translate, type, useI18n } from "@bhojango/mobile-core";
import { router } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { Icon, RiderMark } from "./icons";
import type { Onboarding } from "./rider";
import { night, radius, space, ui } from "./theme";

type Step = Onboarding["steps"][number];

const UPLOADS = new Set(["licence", "insurance"]);
const KNOWN = new Set(["identity", "licence", "payout", "insurance", "background_check"]);

function open(step: Step) {
  if (UPLOADS.has(step.key)) router.push({ pathname: "/document", params: { kind: step.key } });
  else if (step.key === "payout") router.push("/payouts");
}

/** The step's name in the rider's language (the API's words for a step the app doesn't know). */
export function stepTitle(t: Translate, s: Step): string {
  return KNOWN.has(s.key) ? t(`rider.checklist.steps.${s.key}`) : s.title;
}

/** What the step needs or where it stands, in the rider's language. */
export function stepDetail(t: Translate, s: Step): string {
  if (!KNOWN.has(s.key)) return s.detail;
  switch (s.status) {
    case "done":
      return s.key === "payout" ? t("rider.checklist.detail.set_up") : s.key === "background_check" ? t("rider.checklist.detail.cleared")
        : t("rider.checklist.detail.verified");
    case "in_review":
      return s.key === "payout" ? t("rider.checklist.detail.payout_finish") : s.key === "background_check"
        ? t("rider.checklist.detail.background_progress") : t("rider.checklist.detail.checking");
    case "waiting":
      return t("rider.checklist.detail.background_waiting");
    case "rejected":
      return s.detail; // the reviewer's note (or the API's "upload it again")
    default:
      return t(`rider.checklist.detail.needed_${s.key}`);
  }
}

/** The step the big button does: an upload first, then payouts. */
export function nextStep(o: Onboarding): Step | null {
  const actionable = (s: Step) => (s.status === "needed" || s.status === "rejected") && (UPLOADS.has(s.key) || s.key === "payout");
  return o.steps.find((s) => actionable(s) && s.required) ?? o.steps.find(actionable) ?? null;
}

export function Checklist({ onboarding: o, floor, onRefresh, showHeader = true }: {
  onboarding: Onboarding; floor?: string | null; onRefresh: () => void; showHeader?: boolean;
}) {
  const { t } = useI18n();
  const next = nextStep(o);
  const current = next?.key;
  return (
    <SafeAreaView testID="checklist" style={ui.screen} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.body}>
        {showHeader ? (
          <View style={styles.top}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <RiderMark />
              <Text style={ui.bold}>{t("rider.brand")}</Text>
            </View>
            <Pressable accessibilityRole="link" onPress={() => router.push("/sos")} style={styles.help}>
              <Text style={[type.label, { color: night.link }]}>{t("rider.checklist.help")}</Text>
            </Pressable>
          </View>
        ) : null}
        <Text accessibilityRole="header" style={[ui.h1, { marginTop: 24 }]}>
          {o.ready ? t("rider.checklist.ready_title", { name: o.first_name }) : t("rider.checklist.almost_title", { name: o.first_name })}
        </Text>
        <View style={styles.progressRow} accessibilityLabel={t("rider.checklist.progress", { done: o.done, total: o.total })}>
          <View style={styles.track}><View style={[styles.fill, { width: `${(o.done / o.total) * 100}%` }]} /></View>
          <Text style={ui.bold}>{t("rider.checklist.progress_short", { done: o.done, total: o.total })}</Text>
        </View>
        <View style={styles.list}>
          {o.steps.map((s, i) => {
            const done = s.status === "done";
            const now = s.key === current;
            const waiting = s.status === "waiting";
            const tappable = !done && (UPLOADS.has(s.key) || s.key === "payout") && s.status !== "in_review";
            const title = stepTitle(t, s);
            const detail = stepDetail(t, s);
            return (
              <Pressable key={s.key} testID={`step-${s.key}`} disabled={!tappable} onPress={() => open(s)} accessibilityRole={tappable ? "button" : undefined}
                accessibilityLabel={`${title}, ${detail}`}
                style={[styles.item, i < o.steps.length - 1 && styles.itemLine, now && { backgroundColor: night.raised }]}>
                {done ? (
                  <View style={[styles.dot, { backgroundColor: night.doneBg }]}><Icon name="check" size={16} stroke={night.link} width={3} /></View>
                ) : (
                  <View style={[styles.dot, { borderWidth: 2, borderColor: now || s.status === "rejected" ? night.kesar : night.lineStrong }]}>
                    <Text style={[type.label, { color: now ? night.kesar : night.muted }]}>{i + 1}</Text>
                  </View>
                )}
                <View style={{ flex: 1 }}>
                  <Text style={[ui.bold, waiting && { color: night.muted }]}>{title}</Text>
                  <Text style={[ui.muted, now && { color: night.needed }, s.status === "rejected" && { color: night.sosText }]}>{detail}</Text>
                </View>
                {tappable ? <Icon name="chevronRight" size={18} width={2.2} /> : null}
              </Pressable>
            );
          })}
        </View>
        <View style={styles.info}>
          <Text style={ui.note}>
            <Text style={ui.bold}>{t("rider.checklist.how_pay_title")}</Text>{" "}
            {floor ? t("rider.checklist.how_pay_floor", { floor }) : t("rider.checklist.how_pay")}
          </Text>
        </View>
      </ScrollView>
      <View style={{ padding: space[5], paddingTop: 0 }}>
        {next ? (
          <Pressable testID="checklist-next" accessibilityRole="button" onPress={() => open(next)} style={ui.cta}>
            <Text style={ui.ctaText}>
              {next.key === "payout" ? t("rider.checklist.cta_payouts") : next.key === "insurance" ? t("rider.checklist.cta_insurance") : t("rider.checklist.cta_licence")}
            </Text>
          </Pressable>
        ) : (
          <Pressable testID="checklist-refresh" accessibilityRole="button" onPress={onRefresh} style={ui.outline}>
            <Text style={ui.bold}>{o.ready ? t("rider.checklist.continue") : t("rider.checklist.checking_refresh")}</Text>
          </Pressable>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  body: { paddingHorizontal: space[5], paddingBottom: space[6] },
  top: { paddingTop: 16, height: 60, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  help: { minHeight: 44, justifyContent: "center" },
  progressRow: { marginTop: 16, flexDirection: "row", alignItems: "center", gap: 12 },
  track: { flex: 1, height: 8, borderRadius: radius.pill, backgroundColor: night.raised },
  fill: { height: 8, borderRadius: radius.pill, backgroundColor: night.kesar },
  list: { marginTop: 24, borderRadius: 16, backgroundColor: night.surface, overflow: "hidden" },
  item: { flexDirection: "row", alignItems: "center", gap: 16, padding: 16 },
  itemLine: { borderBottomWidth: 1, borderBottomColor: night.raised },
  dot: { width: 32, height: 32, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  info: { marginTop: 16, padding: 16, borderRadius: 16, backgroundColor: night.info, borderWidth: 1, borderColor: night.doneBg },
});
