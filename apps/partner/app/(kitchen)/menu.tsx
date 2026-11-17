// PartnerMenu.html: items by category with "In stock / Sold out today", store
// hours and prep time, and offers the kitchen funds (weekly cap). Tapping a dish
// opens its photo: pick one (library or camera), see the dish exactly as customers
// will (lib/dish.tsx), then save it as the item's image_url. On a phone (portrait,
// lib/layout.ts) it is one column: the search under the title, each dish on two
// lines (name, then price and stock), then the store hours and offers.
import { api, ApiError, field, LoadError, loadErrorText, num, SafeAreaView, type Translate, type, unwrap, useI18n } from "@bhojango/mobile-core";
import * as ImagePicker from "expo-image-picker";
import { useMemo, useState } from "react";
import { ActivityIndicator, Alert, Image, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { imageUri, useFormat, useKitchen, useLoad, type Offer } from "../../lib/data";
import { DishPreview } from "../../lib/dish";
import { useLayout } from "../../lib/layout";
import { Btn, color, Icon, radius, Segmented, t, tone } from "../../lib/ui";
import { menuPhotoUrl, uploadFile } from "../../lib/upload";

type MenuItem = { id: string; name: string; description?: string | null; price: number | string; is_veg?: boolean;
  is_available: boolean; sold_out_today?: boolean; image_url?: string | null; option_groups?: { name: string }[] };
type Menu = { restaurant: { currency: string; avg_prep_minutes?: number }; categories: { name: string; items: MenuItem[] }[]; uncategorized_items: MenuItem[] };
type Hours = { weekly: { weekday: number; opens: string; closes: string }[]; overrides: { day: string; closed: boolean; opens: string | null; closes: string | null; note: string | null }[] };
type Clock = (hhmm: string) => string;

/** A Monday (any will do): weekday d (0 = Monday) is this date + d days, named in the country's locale. */
const MONDAY = "2024-01-01";

/** "Mon – Thu  11:00 am – 11:00 pm" rows: days with the same hours grouped (the country's day names and clock). */
function hourRows(h: Hours, day: (d: number) => string, hm: Clock, closed: string): { days: string; hours: string }[] {
  const by = [0, 1, 2, 3, 4, 5, 6].map((d) => h.weekly.filter((w) => w.weekday === d).map((w) => `${hm(w.opens)} – ${hm(w.closes)}`).join(", ") || closed);
  const rows: { days: string; hours: string }[] = [];
  let start = 0;
  for (let d = 1; d <= 7; d++) {
    if (d === 7 || by[d] !== by[start]) {
      rows.push({ days: start === d - 1 ? day(start) : `${day(start)} – ${day(d - 1)}`, hours: by[start]! });
      start = d;
    }
  }
  return rows;
}

export default function MenuScreen() {
  const { cash, clock, date } = useFormat();
  const { t: tr } = useI18n();
  const { width, narrow } = useLayout();
  const stacked = width < 1000; // a phone (or a small tablet): the menu first, the store panels below
  const kitchen = useKitchen((s) => s.kitchen)!;
  const id = kitchen.id;
  const menu = useLoad(async () => unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/menu", { params: { path: { restaurant_id: id } } })) as unknown as Menu, id);
  const hours = useLoad(async () => unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/hours", { params: { path: { restaurant_id: id } } })) as unknown as Hours, id);
  const today = useLoad(async () => unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/today", { params: { path: { restaurant_id: id } } })), id);
  const offers = useLoad(async () => unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/offers", { params: { path: { restaurant_id: id } } })), id);
  const [cat, setCat] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<MenuItem | null>(null);
  const cur = kitchen.currency;
  const hm: Clock = (hhmm) => clock(`2000-01-01T${hhmm.slice(0, 5)}:00`);
  const day = (d: number) => {
    const x = new Date(`${MONDAY}T12:00:00`);
    x.setDate(x.getDate() + d);
    return date(x, { weekday: "short", day: undefined, month: undefined });
  };

  const more = tr("partner.menu.more");
  const cats = useMemo(() => {
    const m = menu.data;
    if (!m) return [];
    return [...m.categories, ...(m.uncategorized_items.length ? [{ name: more, items: m.uncategorized_items }] : [])];
  }, [menu.data, more]);
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
      Alert.alert(tr("partner.menu.change_failed"), e instanceof ApiError ? e.message : loadErrorText(e, tr).reason);
    }
  }

  async function setPrep(minutes: number) {
    unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/prep-time", { params: { path: { restaurant_id: id } }, body: { minutes } }));
    await today.reload();
  }

  async function endOffer(o: Offer) {
    Alert.alert(tr("partner.offers.end_title", { name: o.name }), tr("partner.offers.end_body"), [{ text: tr("partner.offers.keep"), style: "cancel" }, {
      text: tr("partner.offers.end"), style: "destructive", onPress: async () => {
        offers.setData(unwrap(await api.core.POST("/api/v1/restaurants/{restaurant_id}/offers/{offer_id}/end", {
          params: { path: { restaurant_id: id, offer_id: o.id } } })));
      } }]);
  }

  const prep = today.data ? today.data.prep_minutes - today.data.busy_extra_minutes : 20;
  const itemsPanel = (
    <View style={[s.panel, stacked ? { minHeight: 420 } : { flex: 1.6 }, narrow && s.panelNarrow]} accessibilityLabel={tr("partner.menu.items")}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flexGrow: 0 }} contentContainerStyle={{ gap: 8, paddingBottom: 12 }}>
        {cats.map((c, ci) => {
          const on = !q && c.name === current;
          return (
            <Pressable key={c.name} testID={`category-${ci}`} accessibilityRole="button" accessibilityState={{ selected: on }} onPress={() => { setQ(""); setCat(c.name); }}
              style={[s.chip, on && { backgroundColor: color.kohl, borderColor: color.kohl }]}>
              <Text style={[type.label, { color: on ? color.white : color.kohl }]}>{c.name} · {c.items.length}</Text>
            </Pressable>
          );
        })}
      </ScrollView>
      {narrow ? null : (
        <View style={s.th}>
          <Text style={[type.caption, s.thText, { flex: 1 }]}>{tr("partner.menu.item")}</Text>
          <Text style={[type.caption, s.thText, { width: 96 }]}>{tr("partner.menu.price")}</Text>
          <Text style={[type.caption, s.thText, { width: stacked ? 150 : 190 }]}>{tr("partner.menu.available")}</Text>
        </View>
      )}
      <ScrollView nestedScrollEnabled contentContainerStyle={{ paddingBottom: 12 }}>
        {menu.data && items.length === 0 ? <Text style={[t.muted, { paddingVertical: 16 }]}>{tr("partner.menu.none")}</Text> : null}
        {/* R9: the menu didn't load (offline, our servers): say so and Retry. */}
        {!menu.data && menu.failure ? <LoadError error={menu.failure} onRetry={menu.reload} /> : null}
        {!menu.data && !menu.failure ? <ActivityIndicator accessibilityLabel={tr("common.loading")} color={color.peacock} style={{ paddingVertical: 16 }} /> : null}
        {items.map((i, n) => {
          const inStock = i.is_available && !i.sold_out_today;
          const groups = (i.option_groups ?? []).map((g) => g.name.toLowerCase());
          const price = <Text style={[type.label, num, { width: narrow ? undefined : 96, paddingLeft: narrow ? 0 : 8 }]}>{cash(i.price, cur)}</Text>;
          const stock = (
            <Pressable accessibilityRole="switch" accessibilityState={{ checked: inStock }} accessibilityLabel={tr("partner.menu.in_stock_label", { name: i.name })}
              onPress={() => toggle(i)} style={{ width: narrow ? undefined : stacked ? 150 : 190, flexDirection: "row", alignItems: "center", gap: 10, minHeight: 44 }}>
              <View style={[s.switch, inStock && { backgroundColor: color.peacock }]}><View style={[s.knob, inStock && { left: 22 }]} /></View>
              <Text style={[type.label, { color: inStock ? color.kohl : color.muted, flexShrink: 1 }]}>
                {inStock ? tr("partner.menu.in_stock") : tr("partner.menu.sold_out")}
              </Text>
            </Pressable>
          );
          return (
            <View key={i.id} style={[s.tr, narrow && s.trNarrow]}>
              <Pressable testID={n === 0 ? "menu-item-0" : `menu-item-${i.id}`} accessibilityRole="button"
                accessibilityLabel={tr("partner.photo.open", { name: i.name })} onPress={() => setEditing(i)}
                style={({ pressed }) => [{ flex: narrow ? undefined : 1, flexDirection: "row", gap: 12, alignItems: "center", minHeight: narrow ? 52 : 64 },
                  pressed && { opacity: 0.7 }]}>
                <View style={[s.veg, { borderColor: i.is_veg ? "#2E7D32" : "#8C1D18" }]}><View style={[s.vegDot, { backgroundColor: i.is_veg ? "#2E7D32" : "#8C1D18" }]} /></View>
                <View style={{ flex: 1 }}>
                  <Text style={type.label}>{i.name}</Text>
                  <Text style={t.muted} numberOfLines={1}>
                    {i.sold_out_today ? tr("partner.menu.back_tomorrow") : groups.length ? groups.join(", ") : i.description || (i.is_veg ? tr("common.veg") : "")}
                  </Text>
                </View>
                <View style={[s.photoTag, i.image_url ? s.photoTagOn : null]}>
                  <Text style={[type.caption, { color: i.image_url ? color.peacockDeep : color.muted }]}>
                    {i.image_url ? tr("partner.photo.has_photo") : tr("partner.photo.add_photo")}
                  </Text>
                </View>
              </Pressable>
              {narrow ? (
                // A phone: the price and the stock switch on a second line, under the name.
                <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12, paddingLeft: 28 }}>{price}{stock}</View>
              ) : (
                <>{price}{stock}</>
              )}
            </View>
          );
        })}
      </ScrollView>
      <Text style={[t.muted, { marginTop: 8 }]}>{tr("partner.menu.price_note")}</Text>
    </View>
  );
  const storePanels = (
    <>
      <View testID="hours-panel" style={[s.panel, narrow && s.panelNarrow]} accessibilityLabel={tr("partner.menu.hours")}>
        <Text style={type.h3}>{tr("partner.menu.hours")}</Text>
        {hours.data ? hourRows(hours.data, day, hm, tr("partner.menu.closed")).map((r) => (
          <View key={r.days} style={s.hoursRow}><Text style={t.body}>{r.days}</Text><Text style={[t.label, { flexShrink: 1, textAlign: "right" }]}>{r.hours}</Text></View>
        )) : null}
        {hours.data?.overrides.slice(0, 3).map((o) => (
          <View key={o.day} style={s.hoursRow}>
            <Text style={[t.body, { flexShrink: 1 }]} numberOfLines={1}>{date(o.day)} · {o.note ?? tr("partner.menu.special_hours")}</Text>
            <Text style={[t.label, o.closed && { color: color.chili }]}>{o.closed ? tr("partner.menu.closed") : `${hm(o.opens!)} – ${hm(o.closes!)}`}</Text>
          </View>
        ))}
        <Text style={[t.label, { marginTop: 8 }]}>{tr("partner.menu.prep")}</Text>
        <Segmented label={tr("partner.menu.prep")} value={prep} onChange={(m) => void setPrep(m)}
          options={[15, 20, 25, 30, 40].map((m) => ({ value: m, label: !narrow || m === prep ? tr("partner.orders.minutes", { min: m }) : String(m) }))} />
      </View>

      <View testID="offers-panel" style={[s.panel, narrow && s.panelNarrow]} accessibilityLabel={tr("partner.offers.title")}>
        <Text style={type.h3}>{tr("partner.offers.title")}</Text>
        {(offers.data ?? []).length === 0 ? <Text style={t.muted}>{tr("partner.offers.none")}</Text> : null}
        {(offers.data ?? []).map((o) => {
          const cap = Number(o.weekly_cap ?? 0), used = Number(o.used_this_week);
          return (
            <Pressable key={o.id} onLongPress={() => endOffer(o)} accessibilityHint={tr("partner.offers.long_press")} style={s.offer}>
              <View style={s.hoursRow}>
                <Text style={[type.label, { flexShrink: 1 }]}>{o.name}</Text>
                <Text style={[type.caption, { color: o.live ? color.peacockDeep : tone.kesarInk }]}>
                  {o.paused ? tr("partner.offers.paused") : o.live ? tr("partner.offers.live") : tr("partner.offers.cap_reached")}
                </Text>
              </View>
              <Text style={t.muted}>{describe(o, cur, cash, tr)}</Text>
              {o.paused ? <Text style={[type.label, { color: tone.kesarInk }]}>{o.paused_reason} {tr("partner.offers.paused_note")}</Text> : null}
              <View style={s.track}><View style={[s.fill, { width: `${cap ? Math.min(100, (used / cap) * 100) : 0}%` }]} /></View>
              <View style={s.hoursRow}>
                <Text style={t.muted}>{tr("partner.offers.used", { amount: cash(used, cur) })}</Text>
                <Text style={t.muted}>{tr("partner.offers.cap", { amount: cash(cap, cur) })}</Text>
              </View>
              <Pressable accessibilityRole="button" onPress={() => endOffer(o)}><Text style={[type.label, { color: tone.reject }]}>{tr("partner.offers.end")}</Text></Pressable>
            </Pressable>
          );
        })}
        <Text style={t.muted}>{tr("partner.offers.payout_note")}</Text>
        <Btn testID="create-offer" title={tr("partner.offers.create")} onPress={() => setCreating(true)} />
      </View>
    </>
  );
  return (
    <SafeAreaView testID="menu-screen" edges={["top", "right"]} style={{ flex: 1 }}>
      <View style={[s.header, narrow && s.headerNarrow]}>
        <Text accessibilityRole="header" style={[t.h1, { flex: narrow ? undefined : 1 }]} numberOfLines={1}>{tr("partner.menu.title")}</Text>
        <View style={[s.search, stacked && { width: 220 }, narrow && { width: "100%" }]}>
          <Icon name="search" size={18} stroke={color.muted} />
          <TextInput disableFullscreenUI testID="menu-search" accessibilityLabel={tr("partner.menu.search")} placeholder={tr("partner.menu.search")} placeholderTextColor={color.muted}
            value={q} onChangeText={setQ} style={[type.body, { flex: 1 }]} />
        </View>
      </View>
      {stacked ? (
        <ScrollView testID="menu-scroll" contentContainerStyle={{ padding: narrow ? 12 : 16, gap: narrow ? 12 : 16 }}>
          {itemsPanel}
          {storePanels}
        </ScrollView>
      ) : (
        <View style={s.body}>
          {itemsPanel}
          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ gap: 16 }}>{storePanels}</ScrollView>
        </View>
      )}
      <CreateOffer visible={creating} currency={cur} onClose={() => setCreating(false)} onCreate={async (body) => {
        offers.setData(unwrap(await api.core.POST("/api/v1/restaurants/{restaurant_id}/offers", { params: { path: { restaurant_id: id } }, body })));
        setCreating(false);
      }} />
      {editing ? (
        <DishPhoto key={editing.id} item={editing} currency={cur} kitchenId={id} onClose={() => setEditing(null)}
          onSaved={async () => { setEditing(null); await menu.reload(); }} />
      ) : null}
    </SafeAreaView>
  );
}

/**
 * A dish's photo: the current one (or none), pick another from the library or take
 * one, see the dish row exactly as customers will, then save. Picking uploads the
 * photo (menu_photo: a public file); nothing changes on the menu until "Save photo".
 */
function DishPhoto({ item, currency, kitchenId, onClose, onSaved }: {
  item: MenuItem; currency: string; kitchenId: string; onClose: () => void; onSaved: () => Promise<void>;
}) {
  const { cash } = useFormat();
  const { t: tr } = useI18n();
  const { width, height, narrow } = useLayout();
  const wide = width >= 900;
  // The photo the dish will have: undefined = unchanged, null = removed, else a picked one.
  const [next, setNext] = useState<{ uri: string; url: string | null } | null | undefined>(undefined);
  const [busy, setBusy] = useState<"upload" | "save" | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const currentUri = imageUri(item.image_url);
  const shown = next === undefined ? currentUri : next?.uri ?? null;
  const elsewhere = next === undefined && !!item.image_url && !currentUri; // a website library photo
  const changed = next !== undefined && (next === null ? !!item.image_url : !!next.url);

  async function pick(from: "library" | "camera") {
    setMsg(null);
    const perm = from === "camera" ? await ImagePicker.requestCameraPermissionsAsync() : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      setMsg(from === "camera" ? tr("partner.photo.camera_needed") : tr("partner.photo.photos_needed"));
      return;
    }
    const opts: ImagePicker.ImagePickerOptions = { mediaTypes: ["images"], quality: 0.7, allowsEditing: true, aspect: [14, 13] };
    const r = from === "camera" ? await ImagePicker.launchCameraAsync(opts) : await ImagePicker.launchImageLibraryAsync(opts);
    const a = r.canceled ? null : r.assets[0];
    if (!a) return;
    setNext({ uri: a.uri, url: null });
    setBusy("upload");
    try {
      const up = await uploadFile(a.uri, a.mimeType ?? "image/jpeg", "menu_photo");
      if (!up.public_path) throw new Error("");
      setNext({ uri: a.uri, url: menuPhotoUrl(up.public_path) });
    } catch (e) {
      setNext(undefined);
      setMsg((!(e instanceof TypeError) && (e as Error).message) || tr("partner.upload.failed"));
    } finally {
      setBusy(null);
    }
  }

  async function save() {
    setBusy("save");
    setMsg(null);
    try {
      // "" clears the photo (the API keeps a field it isn't sent): the row goes text-only.
      unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/menu-items/{item_id}", {
        params: { path: { restaurant_id: kitchenId, item_id: item.id } }, body: { image_url: next?.url ?? "" } }));
      await onSaved();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : tr("partner.photo.save_failed"));
      setBusy(null);
    }
  }

  return (
    <Modal visible transparent animationType="fade" supportedOrientations={["landscape", "portrait"]} onRequestClose={onClose}>
      <View style={s.scrim}>
        <View testID="dish-photo" style={[s.editor, { width: Math.min(980, width - (narrow ? 16 : 32)), maxHeight: height - 32 }, narrow && { padding: 18 }]}>
          <ScrollView contentContainerStyle={{ gap: 20 }} keyboardShouldPersistTaps="handled">
            <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
              <Text accessibilityRole="header" style={[t.h1, { flex: 1 }]} numberOfLines={2}>{tr("partner.photo.title", { name: item.name })}</Text>
              <Btn testID="photo-cancel" title={tr("common.cancel")} onPress={onClose} />
            </View>
            <View style={{ flexDirection: wide ? "row" : "column", gap: narrow ? 16 : 24 }}>
              <View style={{ width: wide ? 300 : undefined, gap: 12 }}>
                <Text style={t.label}>{tr("partner.photo.photo")}</Text>
                <View style={s.photoFrame}>
                  {busy === "upload" ? <ActivityIndicator color={color.peacock} /> : shown ? (
                    <PreviewImage uri={shown} label={tr("partner.photo.photo")} />
                  ) : (
                    <Text style={[t.muted, { textAlign: "center", padding: 16 }]}>
                      {elsewhere ? tr("partner.photo.library_photo") : tr("partner.photo.no_photo")}
                    </Text>
                  )}
                </View>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
                  <Btn testID="photo-choose" title={tr("partner.photo.choose")} onPress={() => pick("library")} disabled={!!busy} grow />
                  <Btn testID="photo-take" title={tr("partner.photo.take")} onPress={() => pick("camera")} disabled={!!busy} grow />
                </View>
                {item.image_url || next ? (
                  <Btn testID="photo-remove" title={tr("partner.photo.remove")} kind="danger" disabled={!!busy || next === null} onPress={() => setNext(null)} />
                ) : null}
                <Text style={t.muted}>{tr("partner.photo.tips")}</Text>
              </View>
              <View style={{ flex: 1, gap: 12 }}>
                <Text style={t.label}>{tr("partner.photo.preview")}</Text>
                <View testID="photo-preview" style={[s.previewCard, narrow && { paddingHorizontal: 14 }]}>
                  <DishPreview testID={shown || elsewhere ? "preview-with-photo" : "preview-text-only"} dish={{
                    name: item.name, price: cash(item.price, currency), description: item.description, is_veg: item.is_veg,
                    photo: shown, photoElsewhere: elsewhere, soldOut: !item.is_available || !!item.sold_out_today,
                  }} />
                </View>
                <Text style={t.muted}>{shown || elsewhere ? tr("partner.photo.preview_photo_note") : tr("partner.photo.preview_text_note")}</Text>
              </View>
            </View>
            {msg ? <Text style={[type.small, { color: color.chili }]}>{msg}</Text> : null}
            <View style={{ flexDirection: "row", justifyContent: "flex-end", gap: 12 }}>
              <Btn testID="photo-save" title={next === null ? tr("partner.photo.save_removed") : tr("partner.photo.save")} kind="primary" height={56}
                busy={busy === "save"} disabled={!changed || !!busy} onPress={save} />
            </View>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

/** The picked photo, cropped like the menu row's 112 × 104 tile, larger. */
function PreviewImage({ uri, label }: { uri: string; label: string }) {
  return <Image source={{ uri }} accessibilityLabel={label} style={{ width: "100%", height: "100%" }} resizeMode="cover" />;
}

function describe(o: Offer, cur: string, cash: ReturnType<typeof useFormat>["cash"], tr: Translate) {
  const p = o.params as { percent?: string; amount?: string; min_subtotal?: string };
  const min = Number(p.min_subtotal ?? 0) > 0 ? cash(p.min_subtotal, cur) : null;
  if (o.template === "free_delivery") return min ? tr("partner.offers.free_delivery_over", { amount: min }) : tr("partner.offers.free_delivery_all");
  if (o.template === "percent_off") {
    return min ? tr("partner.offers.percent_over", { percent: Number(p.percent), amount: min }) : tr("partner.offers.percent_all", { percent: Number(p.percent) });
  }
  return min ? tr("partner.offers.flat_over", { off: cash(p.amount, cur), amount: min }) : tr("partner.offers.flat_all", { off: cash(p.amount, cur) });
}

type OfferBody = { template: "free_delivery" | "percent_off" | "flat_off"; name: string; percent?: string; amount?: string; weekly_cap: string };

function CreateOffer({ visible, currency, onClose, onCreate }: { visible: boolean; currency: string; onClose: () => void; onCreate: (b: OfferBody) => Promise<void> }) {
  const [kind, setKind] = useState<OfferBody["template"]>("free_delivery");
  const [value, setValue] = useState("");
  const [cap, setCap] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { cash } = useFormat();
  const { t: tr } = useI18n(); // lib/ui's `t` is the text styles
  const { narrow } = useLayout();
  const ok = Number(cap) > 0 && (kind === "free_delivery" || Number(value) > 0);
  async function save() {
    setBusy(true);
    setError(null);
    const name = kind === "free_delivery" ? tr("partner.offers.free_delivery") : kind === "percent_off"
      ? tr("partner.offers.percent_name", { percent: value }) : tr("partner.offer.amount_off", { amount: cash(value, currency) });
    try {
      await onCreate({ template: kind, name, weekly_cap: cap, ...(kind === "percent_off" ? { percent: value } : kind === "flat_off" ? { amount: value } : {}) });
      setValue("");
      setCap("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : loadErrorText(e, tr).reason);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal visible={visible} transparent animationType="fade" supportedOrientations={["landscape", "portrait"]} onRequestClose={onClose}>
      <View style={s.scrim}>
        <View style={[s.sheet, narrow && { padding: 20 }]} accessibilityLabel={tr("partner.offers.create_title")}>
          <Text style={t.h1}>{tr("partner.offers.create_title")}</Text>
          <Segmented label={tr("partner.offers.kind")} value={kind} onChange={setKind}
            options={[{ value: "free_delivery", label: tr("partner.offers.free_delivery") }, { value: "percent_off", label: tr("partner.offers.percent_off") },
              { value: "flat_off", label: tr("partner.offer.flat_off") }]} />
          {kind !== "free_delivery" ? (
            <TextInput disableFullscreenUI testID="offer-value" accessibilityLabel={kind === "percent_off" ? tr("partner.offers.percent_label") : tr("partner.offers.amount_label")}
              value={value} onChangeText={setValue} keyboardType="numeric"
              placeholder={kind === "percent_off" ? tr("partner.offers.percent_hint") : tr("partner.offers.amount_hint", { amount: cash(50, currency) })}
              placeholderTextColor={color.muted} style={[field.bodyLg, s.input]} />
          ) : null}
          <TextInput disableFullscreenUI testID="offer-cap" accessibilityLabel={tr("partner.offers.cap_label")} value={cap} onChangeText={setCap} keyboardType="numeric"
            placeholder={tr("partner.offers.cap_hint", { amount: cash(5000, currency) })} placeholderTextColor={color.muted} style={[field.bodyLg, s.input]} />
          <Text style={t.muted}>{tr("partner.offers.cap_note")}</Text>
          {error ? <Text style={[type.small, { color: color.chili }]}>{error}</Text> : null}
          <View style={{ flexDirection: "row", gap: 12 }}>
            <Btn title={tr("common.cancel")} onPress={onClose} />
            <Btn testID="offer-start" title={tr("partner.offers.start")} kind="primary" grow busy={busy} disabled={!ok} onPress={save} />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  header: { height: 80, paddingHorizontal: 24, backgroundColor: color.white, borderBottomWidth: 1, borderBottomColor: color.line, flexDirection: "row", alignItems: "center", gap: 16 },
  headerNarrow: { height: undefined, flexDirection: "column", alignItems: "stretch", paddingHorizontal: 16, paddingVertical: 12, gap: 10 },
  search: { width: 320, height: 48, borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.lineStrong, flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 16 },
  body: { flex: 1, flexDirection: "row", padding: 24, gap: 16 },
  panel: { backgroundColor: color.white, borderRadius: radius.card, borderWidth: 1, borderColor: color.line, padding: 20, gap: 10 },
  panelNarrow: { padding: 14 },
  chip: { height: 44, paddingHorizontal: 16, borderRadius: radius.pill, borderWidth: 1.5, borderColor: color.lineStrong, justifyContent: "center" },
  th: { flexDirection: "row", paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: color.line },
  thText: { color: color.muted },
  tr: { flexDirection: "row", alignItems: "center", minHeight: 64, borderBottomWidth: 1, borderBottomColor: color.divider },
  trNarrow: { flexDirection: "column", alignItems: "stretch", paddingBottom: 6 },
  veg: { width: 16, height: 16, borderWidth: 1.5, borderRadius: 3, alignItems: "center", justifyContent: "center" },
  vegDot: { width: 6, height: 6, borderRadius: 3 },
  photoTag: { paddingHorizontal: 10, height: 28, borderRadius: radius.pill, borderWidth: 1, borderColor: color.line, justifyContent: "center" },
  photoTagOn: { borderColor: color.peacockTint, backgroundColor: color.peacockMist },
  switch: { width: 46, height: 26, borderRadius: 13, backgroundColor: color.lineStrong },
  knob: { position: "absolute", top: 3, left: 3, width: 20, height: 20, borderRadius: 10, backgroundColor: color.white },
  hoursRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 },
  offer: { padding: 16, borderRadius: 12, backgroundColor: color.porcelain, gap: 8 },
  track: { height: 6, borderRadius: 3, backgroundColor: color.divider },
  fill: { height: 6, borderRadius: 3, backgroundColor: color.kesar },
  scrim: { flex: 1, backgroundColor: "rgba(17,20,24,0.4)", alignItems: "center", justifyContent: "center" },
  sheet: { width: 560, maxWidth: "92%", backgroundColor: color.white, borderRadius: radius.sheet, padding: 32, gap: 16 },
  editor: { backgroundColor: color.white, borderRadius: radius.sheet, padding: 28 },
  photoFrame: { width: "100%", aspectRatio: 14 / 13, maxHeight: 280, borderRadius: radius.card, overflow: "hidden", backgroundColor: color.porcelain,
    borderWidth: 1.5, borderStyle: "dashed", borderColor: color.lineStrong, alignItems: "center", justifyContent: "center" },
  previewCard: { borderRadius: radius.card, borderWidth: 1, borderColor: color.line, paddingHorizontal: 20, paddingBottom: 8, backgroundColor: color.white },
  input: { height: 56, borderRadius: radius.card, borderWidth: 1.5, borderColor: color.lineStrong, paddingHorizontal: 16 },
});
