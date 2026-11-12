// RiderOnboarding.html: "Almost ready to ride", five steps, one action.
import { router } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon, RiderMark } from "./icons";
import type { Onboarding } from "./rider";
import { night, radius, space, textFont, ui } from "./theme";

type Step = Onboarding["steps"][number];

const UPLOADS = new Set(["licence", "insurance"]);

function open(step: Step) {
  if (UPLOADS.has(step.key)) router.push({ pathname: "/document", params: { kind: step.key, title: step.title } });
  else if (step.key === "payout") router.push("/payouts");
}

/** The step the big button does: an upload first, then payouts. */
export function nextStep(o: Onboarding): Step | null {
  const actionable = (s: Step) => (s.status === "needed" || s.status === "rejected") && (UPLOADS.has(s.key) || s.key === "payout");
  return o.steps.find((s) => actionable(s) && s.required) ?? o.steps.find(actionable) ?? null;
}

export function Checklist({ onboarding: o, floor, onRefresh, showHeader = true }: {
  onboarding: Onboarding; floor?: string | null; onRefresh: () => void; showHeader?: boolean;
}) {
  const next = nextStep(o);
  const current = next?.key;
  return (
    <SafeAreaView style={ui.screen} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.body}>
        {showHeader ? (
          <View style={styles.top}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              <RiderMark />
              <Text style={[ui.bold, { fontSize: 15, ...textFont("700") }]}>BhojanGo Rider</Text>
            </View>
            <Pressable accessibilityRole="link" onPress={() => router.push("/sos")} style={styles.help}>
              <Text style={[textFont("700"), { color: night.link, fontSize: 14 }]}>Help</Text>
            </Pressable>
          </View>
        ) : null}
        <Text accessibilityRole="header" style={[ui.h1, { marginTop: 24 }]}>
          {o.ready ? `You're ready to ride, ${o.first_name}` : `Almost ready to ride, ${o.first_name}`}
        </Text>
        <View style={styles.progressRow} accessibilityLabel={`${o.done} of ${o.total} steps done`}>
          <View style={styles.track}><View style={[styles.fill, { width: `${(o.done / o.total) * 100}%` }]} /></View>
          <Text style={[ui.bold, { fontSize: 14, ...textFont("700") }]}>{o.done} of {o.total}</Text>
        </View>
        <View style={styles.list}>
          {o.steps.map((s, i) => {
            const done = s.status === "done";
            const now = s.key === current;
            const waiting = s.status === "waiting";
            const tappable = !done && (UPLOADS.has(s.key) || s.key === "payout") && s.status !== "in_review";
            return (
              <Pressable key={s.key} disabled={!tappable} onPress={() => open(s)} accessibilityRole={tappable ? "button" : undefined}
                accessibilityLabel={`${s.title}, ${s.detail}`}
                style={[styles.item, i < o.steps.length - 1 && styles.itemLine, now && { backgroundColor: night.raised }]}>
                {done ? (
                  <View style={[styles.dot, { backgroundColor: night.doneBg }]}><Icon name="check" size={16} stroke={night.link} width={3} /></View>
                ) : (
                  <View style={[styles.dot, { borderWidth: 2, borderColor: now || s.status === "rejected" ? night.kesar : night.lineStrong }]}>
                    <Text style={[textFont("800"), { fontSize: 13, color: now ? night.kesar : night.muted }]}>{i + 1}</Text>
                  </View>
                )}
                <View style={{ flex: 1 }}>
                  <Text style={[ui.bold, { fontSize: 16 }, waiting && { color: night.muted }]}>{s.title}</Text>
                  <Text style={[ui.muted, now && { color: night.needed }, s.status === "rejected" && { color: night.sosText }]}>{s.detail}</Text>
                </View>
                {tappable ? <Icon name="chevronRight" size={18} width={2.2} /> : null}
              </Pressable>
            );
          })}
        </View>
        <View style={styles.info}>
          <Text style={[ui.body, { fontSize: 14, lineHeight: 21 }]}>
            <Text style={ui.bold}>How pay works.</Text> You see the full pay before you accept, tips stay 100% yours
            {floor ? `, and ${floor}` : ", and every city has a floor per active hour"}.
          </Text>
        </View>
      </ScrollView>
      <View style={{ padding: space[5], paddingTop: 0 }}>
        {next ? (
          <Pressable accessibilityRole="button" onPress={() => open(next)} style={ui.cta}>
            <Text style={ui.ctaText}>{next.key === "payout" ? "Set up payouts" : `Upload ${next.key === "insurance" ? "insurance" : "licence"}`}</Text>
          </Pressable>
        ) : (
          <Pressable accessibilityRole="button" onPress={onRefresh} style={ui.outline}>
            <Text style={[ui.bold, { fontSize: 16 }]}>{o.ready ? "Continue" : "We're checking your documents · refresh"}</Text>
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
