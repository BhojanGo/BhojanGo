// RiderEarnings.html: the week so far, by day, the hourly floor, today's
// deliveries and the next payout. Money and dates by the country (Markets).
import { inZone, LoadError, num, SafeAreaView, type, useI18n } from "@bhojango/mobile-core";
import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { Icon } from "../../lib/icons";
import { useFormat, useWeek, type Week } from "../../lib/rider";
import { night, radius, space, ui } from "../../lib/theme";

type DateFn = ReturnType<typeof useFormat>["date"];

/** "Nov 10 – Nov 16" or "10 Nov – 16 Nov" (the country's order) for the week [start, end). */
function range(w: Week, date: DateFn) {
  const end = new Date(`${w.period_end}T12:00:00`);
  end.setDate(end.getDate() - 1);
  return `${date(w.period_start)} – ${date(end)}`;
}

/** The day's initial ("M") in the country's locale. */
function dayInitial(iso: string, date: DateFn) {
  return date(iso, { weekday: "narrow", day: undefined, month: undefined });
}

export default function Earnings() {
  const { cash, cityName, date, time } = useFormat();
  const { t, number } = useI18n();
  const { data: w, failure, reload } = useWeek();
  useFocusEffect(useCallback(() => void reload(), [reload]));

  if (!w) {
    return (
      <SafeAreaView style={[ui.screen, styles.center]}>
        {failure ? <LoadError error={failure} onRetry={reload} tone="dark" fill style={{ alignSelf: "stretch" }} />
          : <ActivityIndicator testID="earnings-loading" color={night.kesar} />}
      </SafeAreaView>
    );
  }
  const cur = w.currency;
  const s = w.summary;
  const todayIso = w.today.date; // in the city's time zone
  const max = Math.max(...w.days.map((d) => Number(d.total)), 1);
  const city = cityName(w.city) ?? t("rider.earnings.your_city");
  // A rate from a few minutes of work means nothing: wait for half an hour.
  const perHour = s.per_active_hour && Number(s.active_hours) >= 0.5 ? Number(s.per_active_hour) : null;
  const lines = [...w.today.lines].reverse(); // newest first
  const floor = s.hourly_floor ? Number(s.hourly_floor) : null;
  const topUp = Number(s.floor_top_up);
  const hours = Number(s.active_hours);

  return (
    <SafeAreaView testID="earnings-screen" style={ui.screen} edges={["top"]}>
      {/* The scroll ends above the payout card (R8: the card sat over "Today" when it floated over the list). */}
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: space[6] }}>
        <View style={styles.head}>
          <Text testID="earnings-title" accessibilityRole="header" style={[type.h2, { color: night.text, letterSpacing: -0.3 }]}>
            {t("rider.earnings.title")}
          </Text>
          <Pressable testID="past-weeks" accessibilityRole="button" accessibilityLabel={t("rider.earnings.week_label", { range: range(w, date) })}
            onPress={() => router.push("/payouts")} style={styles.week}>
            <Text style={ui.bold}>{range(w, date)}</Text>
            <Icon name="chevronDown" size={14} width={2.4} />
          </Pressable>
        </View>
        <View style={{ paddingHorizontal: 20, paddingTop: 24 }}>
          <Text style={ui.muted}>{t("rider.earnings.so_far")}</Text>
          <Text testID="week-total" style={[type.display, num, styles.big]}>{cash(w.total, cur)}</Text>
        </View>
        <View style={[ui.stats, styles.box, { borderRadius: 16, backgroundColor: night.surface, paddingVertical: 16 }]}>
          <View style={ui.stat}>
            <Text style={ui.statValue}>{t("rider.earnings.hours", { value: number(hours, hours < 10 ? 1 : 0) })}</Text>
            <Text style={ui.statLabel}>{t("rider.earnings.active")}</Text>
          </View>
          <View style={[ui.stat, styles.mid]}>
            <Text style={ui.statValue}>{number(s.deliveries, 0)}</Text>
            <Text style={ui.statLabel}>{t("rider.earnings.deliveries")}</Text>
          </View>
          <View style={ui.stat}>
            <Text style={ui.statValue}>{cash(s.tips, cur)}</Text>
            <Text style={ui.statLabel}>{t("rider.earnings.tips")}</Text>
          </View>
        </View>

        <View style={[styles.box, styles.chart]}
          accessibilityLabel={t("rider.earnings.daily", { days: w.days.map((d) => `${date(d.date, { weekday: "short" })} ${cash(d.total, cur)}`).join(", ") })}>
          <View style={styles.bars}>
            {w.days.map((d) => {
              const v = Number(d.total);
              const today = d.date === todayIso;
              const future = d.date > todayIso;
              return (
                <View key={d.date} style={styles.barCol}>
                  <Text style={[type.caption, num, { color: today ? night.text : night.muted }]}>{future ? "–" : cash(v, cur)}</Text>
                  <View style={{ width: "100%", borderRadius: 6, height: future || v === 0 ? 4 : Math.max(8, (v / max) * 110),
                    backgroundColor: today ? night.kesar : future ? night.raised : night.line }} />
                </View>
              );
            })}
          </View>
          <View style={[styles.bars, { height: undefined, marginTop: 8 }]}>
            {w.days.map((d) => (
              <Text key={d.date} style={[type.caption, styles.dayLabel, d.date === todayIso && { color: night.text }]}>
                {dayInitial(d.date, date)}
              </Text>
            ))}
          </View>
        </View>

        <View testID="floor-card" style={[styles.box, styles.floor]}>
          <Icon name="shield" size={24} stroke={night.link} />
          <Text style={[ui.note, { flex: 1 }]}>
            {floor == null ? (
              <Text>{t("rider.earnings.floor_none")}</Text>
            ) : perHour == null ? (
              <Text>
                <Text style={ui.bold}>{t("rider.earnings.floor_amount", { amount: cash(floor, cur) })}</Text>
                {" "}{t("rider.earnings.floor_in", { city })}
              </Text>
            ) : (
              <Text>
                <Text style={ui.bold}>{t("rider.earnings.per_hour", { amount: cash(perHour, cur) })}</Text>
                {" "}{topUp > 0
                  ? t("rider.earnings.below_floor", { city, floor: cash(floor, cur), top_up: cash(topUp, cur) })
                  : t("rider.earnings.above_floor", { city, floor: cash(floor, cur) })}
              </Text>
            )}
          </Text>
        </View>

        <View style={{ marginHorizontal: 20, marginTop: 24 }}>
          <Text style={[ui.bold, { marginBottom: 8 }]}>{t("rider.earnings.today")}</Text>
          {lines.length === 0 ? <Text style={ui.muted}>{t("rider.earnings.none_today")}</Text> : null}
          {lines.map((ln, i) => (
            <View key={ln.order_id} style={[styles.line, i < lines.length - 1 && styles.lineBorder]}>
              <View style={{ flex: 1 }}>
                <Text style={ui.bold}>{ln.restaurant_name}{ln.drop_area ? ` → ${ln.drop_area}` : ""}</Text>
                <Text style={[ui.muted, num]}>
                  {[
                    `${time(ln.delivered_at, inZone(w.time_zone))} · ${t("rider.earnings.base", { amount: cash(ln.base, cur) })}`,
                    Number(ln.distance) > 0 ? `${t("rider.earnings.distance")} ${cash(ln.distance, cur)}` : null,
                    Number(ln.waiting) > 0 ? t("rider.earnings.wait", { amount: cash(ln.waiting, cur) }) : null,
                    Number(ln.tip) > 0 ? t("rider.earnings.tip", { amount: cash(ln.tip, cur) }) : null,
                  ].filter(Boolean).join(" + ")}
                </Text>
              </View>
              <Text style={[ui.bold, num]}>{cash(ln.total, cur)}</Text>
            </View>
          ))}
        </View>
      </ScrollView>
      {/* B6: payouts are weekly only; there's no instant cash-out, so no button that suggests one. */}
      <View style={styles.footer} accessibilityLabel={t("rider.earnings.payout_label")}>
        <View style={styles.payout}>
          <Text testID="next-payout" style={ui.bold}>
            {t("rider.earnings.paid_weekly", { day: date(w.payout_date, { weekday: "short" }) })}
          </Text>
          <Text style={[ui.muted, { textAlign: "center" }]}>{t("rider.earnings.no_cashout")}</Text>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: "center", justifyContent: "center" },
  head: { paddingHorizontal: 20, paddingTop: 16, flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  week: { height: 44, paddingHorizontal: 16, borderRadius: radius.pill, backgroundColor: night.surface, flexDirection: "row", alignItems: "center", gap: 6 },
  big: { color: night.text, marginTop: 4 },
  box: { marginHorizontal: 20, marginTop: 16 },
  mid: { borderLeftWidth: 1, borderRightWidth: 1, borderColor: night.line },
  chart: { padding: 20, borderRadius: 16, backgroundColor: night.surface },
  bars: { height: 132, flexDirection: "row", gap: 8, alignItems: "flex-end" },
  barCol: { flex: 1, alignItems: "center", gap: 6 },
  dayLabel: { flex: 1, textAlign: "center", color: night.muted },
  floor: { padding: 16, borderRadius: 16, backgroundColor: night.info, borderWidth: 1, borderColor: night.doneBg, flexDirection: "row", gap: 12, alignItems: "center" },
  line: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: 12, gap: space[3] },
  lineBorder: { borderBottomWidth: 1, borderBottomColor: night.raised },
  footer: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 16, flexDirection: "row", gap: 12, borderTopWidth: 1, borderTopColor: night.raised, backgroundColor: night.ground },
  payout: { flex: 1, minHeight: 64, paddingHorizontal: 16, paddingVertical: 8, gap: 2, borderRadius: radius.card, borderWidth: 1.5, borderColor: night.lineStrong, alignItems: "center", justifyContent: "center", backgroundColor: night.ground },
});
