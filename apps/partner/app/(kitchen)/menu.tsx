// PartnerMenu.html: items by category with "In stock / Sold out today", store
// hours and prep time, and offers the kitchen funds (weekly cap).
import { api, ApiError, unwrap } from "@bhojango/mobile-core";
import { useMemo, useState } from "react";
import { Alert, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { cash, useKitchen, useLoad, type Offer } from "../../lib/data";
import { Btn, color, Icon, radius, Segmented, t, textFont, tone } from "../../lib/ui";

type MenuItem = { id: string; name: string; description?: string | null; price: number | string; is_veg?: boolean;
  is_available: boolean; sold_out_today?: boolean; option_groups?: { name: string }[] };
type Menu = { restaurant: { currency: string; avg_prep_minutes?: number }; categories: { name: string; items: MenuItem[] }[]; uncategorized_items: MenuItem[] };
type Hours = { weekly: { weekday: number; opens: string; closes: string }[]; overrides: { day: string; closed: boolean; opens: string | null; closes: string | null; note: string | null }[] };

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function ampm(hhmm: string) {
  const [h = 0, m = 0] = hhmm.split(":").map(Number);
  return `${((h + 11) % 12) + 1}:${String(m).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`;
}

/** "Mon – Thu  11:00 am – 11:00 pm" rows: days with the same hours grouped. */
function hourRows(h: Hours): { days: string; hours: string }[] {
  const by = DAYS.map((_, d) => h.weekly.filter((w) => w.weekday === d).map((w) => `${ampm(w.opens)} – ${ampm(w.closes)}`).join(", ") || "Closed");
  const rows: { days: string; hours: string }[] = [];
  let start = 0;
  for (let d = 1; d <= 7; d++) {
    if (d === 7 || by[d] !== by[start]) {
      rows.push({ days: start === d - 1 ? DAYS[start]! : `${DAYS[start]} – ${DAYS[d - 1]}`, hours: by[start]! });
      start = d;
    }
  }
  return rows;
}

export default function MenuScreen() {
  const kitchen = useKitchen((s) => s.kitchen)!;
  const id = kitchen.id;
  const menu = useLoad(async () => unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/menu", { params: { path: { restaurant_id: id } } })) as unknown as Menu, id);
  const hours = useLoad(async () => unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/hours", { params: { path: { restaurant_id: id } } })) as unknown as Hours, id);
  const today = useLoad(async () => unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/today", { params: { path: { restaurant_id: id } } })), id);
  const offers = useLoad(async () => unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/offers", { params: { path: { restaurant_id: id } } })), id);
  const [cat, setCat] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(false);
  const cur = kitchen.currency;

  const cats = useMemo(() => {
    const m = menu.data;
    if (!m) return [];
    return [...m.categories, ...(m.uncategorized_items.length ? [{ name: "More", items: m.uncategorized_items }] : [])];
  }, [menu.data]);
  const current = cat ?? cats[0]?.name ?? null;
  const items = (q ? cats.flatMap((c) => c.items) : cats.find((c) => c.name === current)?.items ?? [])
    .filter((i) => !q || i.name.toLowerCase().includes(q.toLowerCase()));

  async function toggle(i: MenuItem) {
    const out = !(i.sold_out_today ?? false);
    try {
      unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/menu-items/{item_id}/sold-out", {
        params: { path: { restaurant_id: id, item_id: i.id } }, body: { sold_out: out } }));
      await menu.reload();
    } catch (e) {
      Alert.alert("Couldn't change it", e instanceof ApiError ? e.message : (e as Error).message);
    }
  }

  async function setPrep(minutes: number) {
    unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/prep-time", { params: { path: { restaurant_id: id } }, body: { minutes } }));
    await today.reload();
  }

  async function endOffer(o: Offer) {
    Alert.alert(`End “${o.name}”?`, "It stops for new orders straight away.", [{ text: "Keep it", style: "cancel" }, {
      text: "End offer", style: "destructive", onPress: async () => {
        offers.setData(unwrap(await api.core.POST("/api/v1/restaurants/{restaurant_id}/offers/{offer_id}/end", {
          params: { path: { restaurant_id: id, offer_id: o.id } } })));
      } }]);
  }

  const prep = today.data ? today.data.prep_minutes - today.data.busy_extra_minutes : 20;
  return (
    <SafeAreaView edges={["top", "right"]} style={{ flex: 1 }}>
      <View style={s.header}>
        <Text accessibilityRole="header" style={[t.h1, { flex: 1 }]}>Menu &amp; store</Text>
        <View style={s.search}>
          <Icon name="search" size={18} stroke={color.muted} />
          <TextInput accessibilityLabel="Search items" placeholder="Search items" placeholderTextColor={color.muted} value={q} onChangeText={setQ}
            style={[textFont("500"), { flex: 1, fontSize: 15 }]} />
        </View>
      </View>
      <View style={s.body}>
        <View style={[s.panel, { flex: 1.6 }]} accessibilityLabel="Menu items">
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flexGrow: 0 }} contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
            {cats.map((c) => {
              const on = !q && c.name === current;
              return (
                <Pressable key={c.name} accessibilityRole="button" accessibilityState={{ selected: on }} onPress={() => { setQ(""); setCat(c.name); }}
                  style={[s.chip, on && { backgroundColor: color.kohl, borderColor: color.kohl }]}>
                  <Text style={[textFont("700"), { fontSize: 14, color: on ? color.white : color.kohl }]}>{c.name} · {c.items.length}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
          <View style={s.th}><Text style={[s.thText, { flex: 1 }]}>Item</Text><Text style={[s.thText, { width: 96 }]}>Price</Text><Text style={[s.thText, { width: 190 }]}>Available</Text></View>
          <ScrollView contentContainerStyle={{ paddingBottom: 12 }}>
            {items.map((i) => {
              const inStock = i.is_available && !i.sold_out_today;
              const groups = (i.option_groups ?? []).map((g) => g.name.toLowerCase());
              return (
                <View key={i.id} style={s.tr}>
                  <View style={{ flex: 1, flexDirection: "row", gap: 12, alignItems: "center" }}>
                    <View style={[s.veg, { borderColor: i.is_veg ? "#2E7D32" : "#8C1D18" }]}><View style={[s.vegDot, { backgroundColor: i.is_veg ? "#2E7D32" : "#8C1D18" }]} /></View>
                    <View style={{ flex: 1 }}>
                      <Text style={[textFont("700"), { fontSize: 15 }]}>{i.name}</Text>
                      <Text style={t.muted} numberOfLines={1}>
                        {i.sold_out_today ? "Back tomorrow, when you open" : groups.length ? groups.join(", ") : i.description || (i.is_veg ? "Vegetarian" : "")}
                      </Text>
                    </View>
                  </View>
                  <Text style={[textFont("700"), { width: 96, fontSize: 15 }]}>{cash(i.price, cur)}</Text>
                  <Pressable accessibilityRole="switch" accessibilityState={{ checked: inStock }} accessibilityLabel={`${i.name} in stock`}
                    onPress={() => toggle(i)} style={{ width: 190, flexDirection: "row", alignItems: "center", gap: 10 }}>
                    <View style={[s.switch, inStock && { backgroundColor: color.peacock }]}><View style={[s.knob, inStock && { left: 22 }]} /></View>
                    <Text style={[textFont("600"), { fontSize: 14, color: inStock ? color.kohl : color.muted }]}>{inStock ? "In stock" : "Sold out today"}</Text>
                  </Pressable>
                </View>
              );
            })}
          </ScrollView>
          <Text style={[t.muted, { marginTop: 8 }]}>Price changes are checked against your partner agreement before they go live.</Text>
        </View>

        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ gap: 16 }}>
          <View style={s.panel} accessibilityLabel="Store hours">
            <Text style={[textFont("800"), { fontSize: 17 }]}>Store hours</Text>
            {hours.data ? hourRows(hours.data).map((r) => (
              <View key={r.days} style={s.hoursRow}><Text style={t.body}>{r.days}</Text><Text style={[t.body, textFont("600")]}>{r.hours}</Text></View>
            )) : null}
            {hours.data?.overrides.slice(0, 3).map((o) => (
              <View key={o.day} style={s.hoursRow}>
                <Text style={[t.body, { flexShrink: 1 }]} numberOfLines={1}>{new Date(`${o.day}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" })} · {o.note ?? "Special hours"}</Text>
                <Text style={[t.body, textFont("600"), o.closed && { color: color.chili }]}>{o.closed ? "Closed" : `${ampm(o.opens!)} – ${ampm(o.closes!)}`}</Text>
              </View>
            ))}
            <Text style={[t.label, { marginTop: 8 }]}>Default prep time</Text>
            <Segmented label="Default prep time" value={prep} onChange={(m) => void setPrep(m)}
              options={[15, 20, 25, 30, 40].map((m) => ({ value: m, label: `${m} min` }))} />
          </View>

          <View style={s.panel} accessibilityLabel="Offers you fund">
            <Text style={[textFont("800"), { fontSize: 17 }]}>Offers you fund</Text>
            {(offers.data ?? []).length === 0 ? <Text style={t.muted}>No offers running. Offers bring new customers; you choose the weekly limit.</Text> : null}
            {(offers.data ?? []).map((o) => {
              const cap = Number(o.weekly_cap ?? 0), used = Number(o.used_this_week);
              return (
                <Pressable key={o.id} onLongPress={() => endOffer(o)} accessibilityHint="Long press to end the offer" style={s.offer}>
                  <View style={s.hoursRow}>
                    <Text style={[textFont("800"), { fontSize: 15 }]}>{o.name}</Text>
                    <Text style={[textFont("800"), { fontSize: 12, color: o.live ? color.peacockDeep : tone.kesarInk }]}>{o.paused ? "Paused by BhojanGo" : o.live ? "Live" : "Cap reached"}</Text>
                  </View>
                  <Text style={t.muted}>{describe(o, cur)}</Text>
                  {o.paused ? <Text style={[textFont("600"), { fontSize: 14, color: tone.kesarInk }]}>{o.paused_reason} Customers don&apos;t see it until we resume it; ask us from Help.</Text> : null}
                  <View style={s.track}><View style={[s.fill, { width: `${cap ? Math.min(100, (used / cap) * 100) : 0}%` }]} /></View>
                  <View style={s.hoursRow}>
                    <Text style={t.muted}>{cash(used, cur)} used this week</Text>
                    <Text style={t.muted}>cap {cash(cap, cur)}</Text>
                  </View>
                  <Pressable accessibilityRole="button" onPress={() => endOffer(o)}><Text style={[textFont("700"), { fontSize: 13, color: tone.reject }]}>End offer</Text></Pressable>
                </Pressable>
              );
            })}
            <Text style={t.muted}>Comes off your weekly payout, itemised on your statement. Stops when the cap is reached.</Text>
            <Btn title="+ Create offer" onPress={() => setCreating(true)} />
          </View>
        </ScrollView>
      </View>
      <CreateOffer visible={creating} currency={cur} onClose={() => setCreating(false)} onCreate={async (body) => {
        offers.setData(unwrap(await api.core.POST("/api/v1/restaurants/{restaurant_id}/offers", { params: { path: { restaurant_id: id } }, body })));
        setCreating(false);
      }} />
    </SafeAreaView>
  );
}

function describe(o: Offer, cur: string) {
  const p = o.params as { percent?: string; amount?: string; min_subtotal?: string };
  const min = Number(p.min_subtotal ?? 0) > 0 ? ` over ${cash(p.min_subtotal, cur)}` : "";
  if (o.template === "free_delivery") return `All orders${min} · you cover the delivery fee`;
  if (o.template === "percent_off") return `${Number(p.percent)}% off orders${min}`;
  return `${cash(p.amount, cur)} off orders${min}`;
}

type OfferBody = { template: "free_delivery" | "percent_off" | "flat_off"; name: string; percent?: string; amount?: string; weekly_cap: string };

function CreateOffer({ visible, currency, onClose, onCreate }: { visible: boolean; currency: string; onClose: () => void; onCreate: (b: OfferBody) => Promise<void> }) {
  const [kind, setKind] = useState<OfferBody["template"]>("free_delivery");
  const [value, setValue] = useState("");
  const [cap, setCap] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sym = currency === "INR" ? "₹" : "$";
  const ok = Number(cap) > 0 && (kind === "free_delivery" || Number(value) > 0);
  async function save() {
    setBusy(true);
    setError(null);
    const name = kind === "free_delivery" ? "Free delivery" : kind === "percent_off" ? `${value}% off` : `${sym}${value} off`;
    try {
      await onCreate({ template: kind, name, weekly_cap: cap, ...(kind === "percent_off" ? { percent: value } : kind === "flat_off" ? { amount: value } : {}) });
      setValue("");
      setCap("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : (e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={s.scrim}>
        <View style={s.sheet} accessibilityLabel="Create offer">
          <Text style={t.h1}>Create an offer you fund</Text>
          <Segmented label="Offer" value={kind} onChange={setKind}
            options={[{ value: "free_delivery", label: "Free delivery" }, { value: "percent_off", label: "% off" }, { value: "flat_off", label: `${sym} off` }]} />
          {kind !== "free_delivery" ? (
            <TextInput testID="offer-value" accessibilityLabel={kind === "percent_off" ? "Percent off" : "Amount off"} value={value} onChangeText={setValue}
              keyboardType="numeric" placeholder={kind === "percent_off" ? "Percent off, e.g. 10" : `Amount off, e.g. ${sym}50`} placeholderTextColor={color.muted} style={[textFont("600"), s.input]} />
          ) : null}
          <TextInput testID="offer-cap" accessibilityLabel="Weekly cap" value={cap} onChangeText={setCap} keyboardType="numeric"
            placeholder={`Weekly cap, e.g. ${sym}5,000`} placeholderTextColor={color.muted} style={[textFont("600"), s.input]} />
          <Text style={t.muted}>It starts now and stops each week when the cap is used; it starts again on Monday.</Text>
          {error ? <Text style={[textFont("600"), { color: color.chili }]}>{error}</Text> : null}
          <View style={{ flexDirection: "row", gap: 12 }}>
            <Btn title="Cancel" onPress={onClose} />
            <Btn title="Start offer" kind="primary" grow busy={busy} disabled={!ok} onPress={save} />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  header: { height: 80, paddingHorizontal: 24, backgroundColor: color.white, borderBottomWidth: 1, borderBottomColor: color.line, flexDirection: "row", alignItems: "center", gap: 16 },
  search: { width: 320, height: 48, borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.lineStrong, flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 16 },
  body: { flex: 1, flexDirection: "row", padding: 24, gap: 16 },
  panel: { backgroundColor: color.white, borderRadius: radius.card, borderWidth: 1, borderColor: color.line, padding: 20, gap: 10 },
  chip: { height: 44, paddingHorizontal: 16, borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.lineStrong, justifyContent: "center" },
  th: { flexDirection: "row", paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: color.line },
  thText: { ...textFont("700"), fontSize: 12, color: color.muted, textTransform: "uppercase", letterSpacing: 0.6 },
  tr: { flexDirection: "row", alignItems: "center", minHeight: 64, borderBottomWidth: 1, borderBottomColor: color.divider },
  veg: { width: 16, height: 16, borderWidth: 1.5, borderRadius: 3, alignItems: "center", justifyContent: "center" },
  vegDot: { width: 6, height: 6, borderRadius: 3 },
  switch: { width: 46, height: 26, borderRadius: 13, backgroundColor: color.lineStrong },
  knob: { position: "absolute", top: 3, left: 3, width: 20, height: 20, borderRadius: 10, backgroundColor: color.white },
  hoursRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 },
  offer: { padding: 16, borderRadius: 12, backgroundColor: color.porcelain, gap: 8 },
  track: { height: 6, borderRadius: 3, backgroundColor: color.divider },
  fill: { height: 6, borderRadius: 3, backgroundColor: color.kesar },
  scrim: { flex: 1, backgroundColor: "rgba(17,20,24,0.4)", alignItems: "center", justifyContent: "center" },
  sheet: { width: 560, backgroundColor: color.white, borderRadius: radius.sheet, padding: 32, gap: 16 },
  input: { height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: 16, fontSize: 17 },
});
