// RiderEarnings.html: the week so far, by day, the hourly floor, today's
// deliveries and the next payout.
import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Icon } from "../../lib/icons";
import { CITY_NAMES, cash, useWeek, type Week } from "../../lib/rider";
import { displayFont, night, radius, space, textFont, ui } from "../../lib/theme";

const DAY = ["M", "T", "W", "T", "F", "S", "S"];

function md(iso: string, opts: Intl.DateTimeFormatOptions) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("en-US", opts);
}

function range(w: Week) {
  const end = new Date(`${w.period_end}T12:00:00`);
  end.setDate(end.getDate() - 1);
  const a = md(w.period_start, { month: "short", day: "numeric" });
  const sameMonth = end.getMonth() === new Date(`${w.period_start}T12:00:00`).getMonth();
  return `${a}–${end.toLocaleDateString("en-US", sameMonth ? { day: "numeric" } : { month: "short", day: "numeric" })}`;
}

export default function Earnings() {
  const { data: w, error, reload } = useWeek();
  useFocusEffect(useCallback(() => void reload(), [reload]));

  if (!w) {
    return <SafeAreaView style={[ui.screen, styles.center]}>{error ? <Text style={ui.body}>{error}</Text> : <ActivityIndicator color={night.kesar} />}</SafeAreaView>;
  }
  const cur = w.currency;
  const s = w.summary;
  const todayIso = w.today.date; // in the city's time zone
  const max = Math.max(...w.days.map((d) => Number(d.total)), 1);
  const city = w.city ? CITY_NAMES[w.city] ?? w.city : "your city";
  // A rate from a few minutes of work means nothing: wait for half an hour.
  const perHour = s.per_active_hour && Number(s.active_hours) >= 0.5 ? Number(s.per_active_hour) : null;
  const lines = [...w.today.lines].reverse(); // newest first
  const floor = s.hourly_floor ? Number(s.hourly_floor) : null;
  const topUp = Number(s.floor_top_up);
  const hours = Number(s.active_hours);

  return (
    <SafeAreaView style={ui.screen} edges={["top"]}>
      <ScrollView contentContainerStyle={{ paddingBottom: 110 }}>
        <View style={styles.head}>
          <Text accessibilityRole="header" style={[displayFont("600"), { color: night.text, fontSize: 22, letterSpacing: -0.3 }]}>Earnings</Text>
          <Pressable accessibilityRole="button" accessibilityLabel={`Week of ${range(w)}. Past weeks`} onPress={() => router.push("/payouts")} style={styles.week}>
            <Text style={[ui.bold, { fontSize: 14, ...textFont("700") }]}>{range(w)}</Text>
            <Icon name="chevronDown" size={14} width={2.4} />
          </Pressable>
        </View>
        <View style={{ paddingHorizontal: 20, paddingTop: 24 }}>
          <Text style={[ui.muted, { fontSize: 14 }]}>This week so far</Text>
          <Text testID="week-total" style={[displayFont("600"), styles.big]}>{cash(w.total, cur)}</Text>
        </View>
        <View style={[ui.stats, styles.box, { borderRadius: 16, backgroundColor: night.surface, paddingVertical: 16 }]}>
          <View style={ui.stat}><Text style={[ui.statValue, { fontSize: 18 }]}>{hours < 10 ? hours.toFixed(1) : Math.round(hours)} h</Text><Text style={ui.statLabel}>active</Text></View>
          <View style={[ui.stat, styles.mid]}><Text style={[ui.statValue, { fontSize: 18 }]}>{s.deliveries}</Text><Text style={ui.statLabel}>deliveries</Text></View>
          <View style={ui.stat}><Text style={[ui.statValue, { fontSize: 18 }]}>{cash(s.tips, cur, 0)}</Text><Text style={ui.statLabel}>tips</Text></View>
        </View>

        <View style={[styles.box, styles.chart]} accessibilityLabel={`Daily earnings: ${w.days.map((d, i) => `${DAY[i]} ${cash(d.total, cur, 0)}`).join(", ")}`}>
          <View style={styles.bars}>
            {w.days.map((d) => {
              const v = Number(d.total);
              const today = d.date === todayIso;
              const future = d.date > todayIso;
              return (
                <View key={d.date} style={styles.barCol}>
                  <Text style={[textFont(today ? "800" : "400"), { fontSize: 11, color: today ? night.text : night.muted }]}>{future ? "–" : cash(v, cur, 0)}</Text>
                  <View style={{ width: "100%", borderRadius: 6, height: future || v === 0 ? 4 : Math.max(8, (v / max) * 110),
                    backgroundColor: today ? night.kesar : future ? night.raised : night.line }} />
                </View>
              );
            })}
          </View>
          <View style={[styles.bars, { height: undefined, marginTop: 8 }]}>
            {w.days.map((d, i) => (
              <Text key={d.date} style={[textFont(d.date === todayIso ? "800" : "400"), styles.dayLabel, d.date === todayIso && { color: night.text }]}>{DAY[i]}</Text>
            ))}
          </View>
        </View>

        <View style={[styles.box, styles.floor]}>
          <Icon name="shield" size={24} stroke={night.link} />
          <Text style={[ui.body, { flex: 1, fontSize: 14, lineHeight: 20 }]}>
            {floor == null ? (
              <Text>Pay per active hour shows here once you&apos;ve delivered this week.</Text>
            ) : perHour == null ? (
              <Text><Text style={ui.bold}>{cash(floor, cur)} per active hour floor</Text> in {city}. Short weeks get topped up.</Text>
            ) : topUp > 0 ? (
              <Text><Text style={ui.bold}>{cash(perHour, cur)} per active hour</Text> — below {city}&apos;s {cash(floor, cur)} floor, so we add {cash(topUp, cur)}.</Text>
            ) : (
              <Text><Text style={ui.bold}>{cash(perHour, cur)} per active hour</Text> — above {city}&apos;s {cash(floor, cur)} floor. Short weeks get topped up.</Text>
            )}
          </Text>
        </View>

        <View style={{ marginHorizontal: 20, marginTop: 24 }}>
          <Text style={[ui.bold, { fontSize: 15, marginBottom: 8 }]}>Today</Text>
          {lines.length === 0 ? <Text style={ui.muted}>No deliveries yet today.</Text> : null}
          {lines.map((ln, i) => (
            <View key={ln.order_id} style={[styles.line, i < lines.length - 1 && styles.lineBorder]}>
              <View style={{ flex: 1 }}>
                <Text style={[ui.bold, textFont("700")]}>{ln.restaurant_name}{ln.drop_area ? ` → ${ln.drop_area}` : ""}</Text>
                <Text style={[ui.muted, { fontSize: 12 }]}>
                  {new Date(ln.delivered_at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }).toLowerCase()} · base {cash(ln.base, cur)}
                  {Number(ln.distance) > 0 ? ` + ${cur === "USD" ? "miles" : "km"} ${cash(ln.distance, cur)}` : ""}
                  {Number(ln.waiting) > 0 ? ` + wait ${cash(ln.waiting, cur)}` : ""}
                  {Number(ln.tip) > 0 ? ` + tip ${cash(ln.tip, cur)}` : ""}
                </Text>
              </View>
              <Text style={ui.bold}>{cash(ln.total, cur)}</Text>
            </View>
          ))}
        </View>
      </ScrollView>
      <View style={styles.footer}>
        <View style={styles.payout}>
          <Text style={[ui.bold, { fontSize: 14 }]}>Payout {md(w.payout_date, { weekday: "short", month: "short", day: "numeric" })}</Text>
          <Text style={[ui.muted, { fontSize: 12 }]}>to your bank</Text>
        </View>
        <Pressable accessibilityRole="button" style={[ui.cta, { flex: 1, height: 56 }]}
          onPress={() => Alert.alert("Cash out now", "Instant cash-out isn't available yet. Your pay goes to your bank every Monday.")}>
          <Text style={[ui.ctaText, { fontSize: 16 }]}>Cash out now</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: "center", justifyContent: "center" },
  head: { paddingHorizontal: 20, paddingTop: 16, flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  week: { height: 44, paddingHorizontal: 16, borderRadius: radius.pill, backgroundColor: night.surface, flexDirection: "row", alignItems: "center", gap: 6 },
  big: { color: night.text, fontSize: 56, letterSpacing: -2, lineHeight: 58, marginTop: 4, fontVariant: ["tabular-nums"] },
  box: { marginHorizontal: 20, marginTop: 16 },
  mid: { borderLeftWidth: 1, borderRightWidth: 1, borderColor: night.line },
  chart: { padding: 20, borderRadius: 16, backgroundColor: night.surface },
  bars: { height: 132, flexDirection: "row", gap: 8, alignItems: "flex-end" },
  barCol: { flex: 1, alignItems: "center", gap: 6 },
  dayLabel: { flex: 1, textAlign: "center", fontSize: 12, color: night.muted },
  floor: { padding: 16, borderRadius: 16, backgroundColor: night.info, borderWidth: 1, borderColor: night.doneBg, flexDirection: "row", gap: 12, alignItems: "center" },
  line: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 12, gap: space[3] },
  lineBorder: { borderBottomWidth: 1, borderBottomColor: night.raised },
  footer: { position: "absolute", left: 20, right: 20, bottom: 16, flexDirection: "row", gap: 12 },
  payout: { flex: 1, height: 56, borderRadius: radius.pill, borderWidth: 1.5, borderColor: night.lineStrong, alignItems: "center", justifyContent: "center", backgroundColor: night.ground },
});
