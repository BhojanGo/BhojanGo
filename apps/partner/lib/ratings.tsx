// The kitchen's ratings on the dashboard (round 4): a chip in the orders header
// ("★ 4.6 · 23 ratings", or "New" until 5 ratings, as customers see it on the
// website) that opens the summary: the average, how many gave each star, and the
// latest comments (no customer names). GET /restaurants/{id}/ratings/summary.
import { useI18n } from "@bhojango/mobile-core";
import { useEffect, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";

import { getRatingSummary, type RatingSummary } from "./data";
import { Btn, color, displayFont, radius, t, textFont, tone } from "./ui";

const REFRESH_MS = 5 * 60_000; // ratings change slowly; the board polls orders, not this

/** The kitchen's rating summary, loaded once and every few minutes. */
export function useRatingSummary(kitchenId: string | undefined) {
  const [data, setData] = useState<RatingSummary | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    if (!kitchenId) return;
    let live = true;
    const load = async () => {
      try {
        const d = await getRatingSummary(kitchenId);
        if (live) {
          setData(d);
          setError(false);
        }
      } catch {
        if (live) setError(true);
      }
    };
    void load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [kitchenId]);
  return { data, error };
}

/** "★ 4.6 · 23 ratings" or "New · 3 ratings": the header chip; opens the summary. */
export function RatingChip({ kitchenId }: { kitchenId: string }) {
  const { t: tr, number } = useI18n();
  const { data } = useRatingSummary(kitchenId);
  const [open, setOpen] = useState(false);
  if (!data) return null;
  const d = data.rating_display;
  const label = d.new
    ? tr("partner.ratings.chip_new", { count: data.count })
    : tr("partner.ratings.chip", { stars: number(d.stars ?? 0, 1), count: data.count });
  return (
    <>
      <Pressable testID="rating-chip" accessibilityRole="button" accessibilityLabel={label} onPress={() => setOpen(true)}
        style={({ pressed }) => [s.chip, pressed && { opacity: 0.85 }]}>
        <Text style={[textFont("800"), { fontSize: 14, color: d.new ? color.kohl : tone.kesarInk }]} numberOfLines={1}>{label}</Text>
      </Pressable>
      <Modal visible={open} transparent animationType="fade" supportedOrientations={["landscape", "portrait"]} onRequestClose={() => setOpen(false)}>
        <Pressable style={s.scrim} onPress={() => setOpen(false)}>
          <Pressable onPress={() => undefined} style={{ width: "100%", alignItems: "center" }}>
            <RatingSummaryCard summary={data} onClose={() => setOpen(false)} />
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

/** The summary: big average (or "New"), the star bars, the latest comments. */
export function RatingSummaryCard({ summary, onClose }: { summary: RatingSummary; onClose?: () => void }) {
  const { t: tr, number, date } = useI18n();
  const { width, height } = useWindowDimensions();
  const wide = width >= 900;
  const d = summary.rating_display;
  const most = Math.max(1, ...summary.distribution);
  return (
    <View testID="rating-summary" style={[s.card, { width: Math.min(760, width - 32), maxHeight: height - 48 }]}>
      <ScrollView contentContainerStyle={{ gap: 16 }}>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <Text accessibilityRole="header" style={t.h1}>{tr("partner.ratings.title")}</Text>
          {onClose ? <Btn testID="rating-close" title={tr("common.close")} onPress={onClose} /> : null}
        </View>
        <View style={{ flexDirection: wide ? "row" : "column", gap: 24 }}>
          <View style={{ width: wide ? 220 : undefined, gap: 6 }}>
            {d.new ? (
              <>
                <Text testID="rating-average" style={[displayFont("600"), s.big]}>{tr("common.new")}</Text>
                <Text style={t.muted}>{tr("partner.ratings.new_until", { count: summary.count })}</Text>
              </>
            ) : (
              <>
                <Text testID="rating-average" style={[displayFont("600"), s.big]}>★ {number(d.stars ?? 0, 1)}</Text>
                <Text style={t.muted}>{tr("partner.ratings.from", { count: summary.count })}</Text>
              </>
            )}
            {summary.count > 0 && summary.average != null && d.new ? (
              <Text style={t.body}>{tr("partner.ratings.average_so_far", { stars: number(summary.average, 1) })}</Text>
            ) : null}
          </View>
          <View testID="rating-distribution" style={{ flex: 1, gap: 8 }} accessibilityLabel={tr("partner.ratings.distribution")}>
            {[5, 4, 3, 2, 1].map((star) => {
              const n = summary.distribution[star - 1] ?? 0;
              return (
                <View key={star} testID={`rating-bar-${star}`} style={s.barRow}
                  accessibilityLabel={tr("partner.ratings.bar", { stars: star, count: n })}>
                  <Text style={[textFont("700"), { width: 36, fontSize: 14 }]}>{star} ★</Text>
                  <View style={s.track}><View style={[s.fill, { width: `${(n / most) * 100}%` }]} /></View>
                  <Text style={[textFont("600"), { width: 44, textAlign: "right", fontSize: 14, color: color.muted }]}>{number(n, 0)}</Text>
                </View>
              );
            })}
          </View>
        </View>
        <View style={{ gap: 8 }}>
          <Text style={[textFont("800"), { fontSize: 16 }]}>{tr("partner.ratings.recent")}</Text>
          {summary.recent.length === 0 ? <Text style={t.muted}>{tr("partner.ratings.no_comments")}</Text> : null}
          {summary.recent.map((c, i) => (
            <View key={i} testID={`rating-comment-${i}`} style={s.comment}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 12 }}>
                <Text style={[textFont("800"), { fontSize: 14, color: tone.kesarInk }]}
                  accessibilityLabel={tr("partner.ratings.stars_label", { count: c.stars })}>{"★".repeat(c.stars)}</Text>
                <Text style={t.muted}>{date(c.created_at)}</Text>
              </View>
              <Text style={t.body}>{c.comment}</Text>
            </View>
          ))}
          <Text style={t.muted}>{tr("partner.ratings.privacy")}</Text>
        </View>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  chip: { height: 48, paddingHorizontal: 16, borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.lineStrong,
    backgroundColor: color.white, justifyContent: "center", maxWidth: 220 },
  scrim: { flex: 1, backgroundColor: "rgba(17,20,24,0.4)", alignItems: "center", justifyContent: "center" },
  card: { backgroundColor: color.white, borderRadius: radius.sheet, padding: 28 },
  big: { fontSize: 44, letterSpacing: -1, color: color.kohl },
  barRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  track: { flex: 1, height: 10, borderRadius: 5, backgroundColor: color.divider, overflow: "hidden" },
  fill: { height: 10, borderRadius: 5, backgroundColor: color.kesar },
  comment: { padding: 14, borderRadius: 12, backgroundColor: color.porcelain, gap: 4 },
});
