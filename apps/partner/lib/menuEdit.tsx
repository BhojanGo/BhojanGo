// R43: menu editing on the tablet. The dish editor (name, description, price, photo, category, veg or non-veg
// (where the country's food licence asks for it), spice, on the menu, sold out today, when it's served, its option groups), option groups (prices, required
// or optional, at least / at most), categories (add, rename, hide, when they're served, drag to reorder) and the
// menu's history (who, when, old -> new). Prices follow the API's rules before saving: more than 0, cents at most,
// whole units where the currency has no cents in use; a change of more than 50% asks first (the API answers 409 PRICE_CONFIRM otherwise).
import { api, ApiError, errorMessage, num, priceRule, type Translate, type, unwrap, useI18n } from "@bhojango/mobile-core";
import { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Alert, Animated, Modal, PanResponder, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import { useFormat } from "./data";
import { useLayout } from "./layout";
import { Btn, color, Segmented, t } from "./ui";

export type ManageCategory = { id: string; name: string; description: string | null; sort_order: number; is_active: boolean;
  available_from: string | null; available_until: string | null };
export type ManageItem = { id: string; name: string; description: string; price: string; image_url: string | null;
  category_id: string | null; category: string; is_veg: boolean; spice_level: number | null; is_available: boolean;
  sold_out_today: boolean; available_from: string | null; available_until: string | null; sort_order: number; option_group_ids: string[] };
export type ManageOption = { id?: string; name: string; price: string; is_default: boolean; is_available: boolean };
export type ManageGroup = { id: string; name: string; min_picks: number; max_picks: number; options: ManageOption[] };
export type Manage = { restaurant_id: string; currency: string; country: string; whole_units: boolean; veg_marks: boolean;
  categories: ManageCategory[]; items: ManageItem[]; option_groups: ManageGroup[] };
export type Change = { id: string; at: string; who: string; actor_kind: string; entity: string; entity_id: string | null;
  name: string; action: string; changes: { field: string; old: unknown; new: unknown }[] };

const r = (rid: string) => ({ params: { path: { restaurant_id: rid } } });

export async function loadManage(rid: string): Promise<Manage> {
  return unwrap(await api.core.GET("/api/v1/restaurants/{restaurant_id}/menu/manage", r(rid))) as unknown as Manage;
}

/** Why a price can't be saved (the API's rules), in the tablet's language; null when fine. */
export function priceProblem(text: string, whole: boolean, tr: Translate, allowZero = false): string | null {
  const p = priceRule(text, whole, allowZero);
  return p === "required" ? tr("partner.edit.price_required") : p === "whole" ? tr("partner.edit.price_whole")
    : p === "cents" ? tr("partner.edit.price_cents") : null;
}

/** R44: a form's message. A rule problem shows after the first Save and follows the fields live (gone the moment the value is
 * valid); the server's answer to a save is dropped as soon as anything is edited. Before, the message was set on Save only and
 * stayed after the field was fixed: "12.505", Save, then "12.50" still said "at most 2 decimals". */
function useFormMsg(problem: string | null, fields: unknown[]) {
  const [tried, setTried] = useState(false);
  const [server, setServerAt] = useState<{ msg: string; at: string } | null>(null);
  const key = JSON.stringify(fields);
  const setServer = (msg: string | null) => setServerAt(msg ? { msg, at: key } : null);
  return { msg: (tried ? problem : null) ?? (server?.at === key ? server.msg : null), setServer, check: () => { setTried(true); return problem; } };
}

const HM = /^([01]\d|2[0-3]):[0-5]\d$/;
export const okTime = (v: string) => HM.test(v.trim());

function detail(e: unknown): Record<string, unknown> | null {
  const d = e instanceof ApiError ? (e.body as { detail?: unknown } | undefined)?.detail : null;
  return d && typeof d === "object" ? (d as Record<string, unknown>) : null;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <View style={{ gap: 6 }}><Text style={t.label}>{label}</Text>{children}</View>;
}

function Toggle({ on, label, onPress, testID }: { on: boolean; label: string; onPress: () => void; testID?: string }) {
  return (
    <Pressable testID={testID} accessibilityRole="switch" accessibilityState={{ checked: on }} accessibilityLabel={label} onPress={onPress}
      style={{ flexDirection: "row", alignItems: "center", gap: 10, minHeight: 44 }}>
      <View style={[s.switch, on && { backgroundColor: color.peacock }]}><View style={[s.knob, on && { left: 22 }]} /></View>
      <Text style={[type.label, { flexShrink: 1 }]}>{label}</Text>
    </Pressable>
  );
}

function Sheet({ testID, title, onClose, children, footer, msg }: {
  testID: string; title: string; onClose: () => void; children: React.ReactNode; footer?: React.ReactNode; msg?: string | null;
}) {
  const { tr } = useTr();
  const { width, height, narrow } = useLayout();
  return (
    <Modal visible transparent animationType="fade" supportedOrientations={["landscape", "portrait"]} onRequestClose={onClose}>
      <View style={s.scrim}>
        <View testID={testID} style={[s.sheet, { width: Math.min(900, width - (narrow ? 16 : 32)), maxHeight: height - 32 }, narrow && { padding: 18 }]}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 12, marginBottom: 12 }}>
            <Text accessibilityRole="header" style={[t.h1, { flex: 1 }]} numberOfLines={2}>{title}</Text>
            <Btn testID={`${testID}-close`} title={tr("common.cancel")} onPress={onClose} />
          </View>
          <ScrollView contentContainerStyle={{ gap: 16, paddingBottom: 8 }} keyboardShouldPersistTaps="handled">{children}</ScrollView>
          {/* the save's answer next to Save, so it's seen on any screen (a long form scrolls) */}
          {msg ? <Text testID={`${testID}-error`} accessibilityRole="alert" style={[type.label, { color: color.chili, marginTop: 12 }]}>{msg}</Text> : null}
          {footer ? <View style={{ flexDirection: "row", justifyContent: "flex-end", flexWrap: "wrap", gap: 12, marginTop: 12 }}>{footer}</View> : null}
        </View>
      </View>
    </Modal>
  );
}

function useTr() {
  const { t: tr } = useI18n();
  return { tr };
}

// ── the dish editor ──────────────────────────────────────────────────────────

export function DishEditor({ data, dish, onClose, onSaved, onPhoto, onHistory }: {
  data: Manage; dish: ManageItem | null; onClose: () => void; onSaved: () => Promise<void>;
  onPhoto: (d: ManageItem) => void; onHistory: (d: ManageItem) => void;
}) {
  const { tr } = useTr();
  const { cash } = useFormat();
  const rid = data.restaurant_id;
  const vegMarks = data.veg_marks;
  const [name, setName] = useState(dish?.name ?? "");
  const [description, setDescription] = useState(dish?.description ?? "");
  const [price, setPrice] = useState(dish ? (data.whole_units ? String(Math.round(Number(dish.price))) : dish.price) : "");
  const [categoryId, setCategoryId] = useState<string | null>(dish?.category_id ?? data.categories[0]?.id ?? null);
  const [veg, setVeg] = useState(dish?.is_veg ?? false);
  const [spice, setSpice] = useState<number>(dish?.spice_level ?? 0);
  const [onMenu, setOnMenu] = useState(dish?.is_available ?? true);
  const [soldOut, setSoldOut] = useState(dish?.sold_out_today ?? false);
  const [timed, setTimed] = useState<"all" | "set">(dish?.available_from ? "set" : "all");
  const [from, setFrom] = useState(dish?.available_from ?? "07:00");
  const [until, setUntil] = useState(dish?.available_until ?? "11:00");
  const [groups, setGroups] = useState<string[]>(dish?.option_group_ids ?? []);
  const [group, setGroup] = useState<ManageGroup | "new" | null>(null);
  const [allGroups, setAllGroups] = useState(data.option_groups);
  const [busy, setBusy] = useState(false);

  const problem = name.trim().length < 2 ? tr("partner.edit.name_required")
    : priceProblem(price, data.whole_units, tr)
    ?? (timed === "set" && (!okTime(from) || !okTime(until) || from === until) ? tr("partner.edit.time_invalid") : null);
  const { msg, setServer: setMsg, check } = useFormMsg(problem, [name, description, price, categoryId, veg, spice, onMenu, soldOut, timed, from, until, groups]);

  async function save(confirmed = false): Promise<void> {
    if (check()) return;
    setBusy(true);
    setMsg(null);
    const cat = data.categories.find((c) => c.id === categoryId);
    const body = {
      name: name.trim(), description: description.trim(), price: price.trim().replace(",", "."), category_id: categoryId ?? undefined,
      is_veg: veg, spice_level: spice || null, is_available: onMenu,
      available_from: timed === "set" ? from.trim() : null, available_until: timed === "set" ? until.trim() : null,
    };
    try {
      let id = dish?.id;
      if (dish) {
        unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/menu-items/{item_id}", {
          params: { path: { restaurant_id: rid, item_id: dish.id } }, body: { ...body, confirm_price_change: confirmed } }));
      } else {
        const made = unwrap(await api.core.POST("/api/v1/restaurants/{restaurant_id}/menu-items", {
          ...r(rid), body: { ...body, category: cat?.name ?? tr("partner.menu.more"), description: body.description } }));
        id = (made as { id: string }).id;
        if (!onMenu) {
          unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/menu-items/{item_id}", {
            params: { path: { restaurant_id: rid, item_id: id } }, body: { is_available: false } }));
        }
      }
      if (JSON.stringify(groups) !== JSON.stringify(dish?.option_group_ids ?? [])) {
        unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/menu-items/{item_id}/option-groups", {
          params: { path: { restaurant_id: rid, item_id: id! } }, body: { group_ids: groups } }));
      }
      if (dish && soldOut !== dish.sold_out_today) {
        unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/menu-items/{item_id}/sold-out", {
          params: { path: { restaurant_id: rid, item_id: id! } }, body: { sold_out: soldOut } }));
      }
      await onSaved();
    } catch (e) {
      const d = detail(e);
      setBusy(false);
      if (d?.code === "PRICE_CONFIRM" && dish) {
        // More than 50% up or down: say how much, from what to what, and save only on "Change price".
        Alert.alert(tr("partner.edit.big_title", { percent: Number(d.percent) }),
          tr("partner.edit.big_body", { name: name.trim(), old: cash(String(d.old), data.currency), new: cash(String(d.new), data.currency) }),
          [{ text: tr("partner.edit.keep"), style: "cancel" }, { text: tr("partner.edit.big_ok"), onPress: () => void save(true) }]);
        return;
      }
      setMsg(e instanceof ApiError ? errorMessage(e.body, tr("partner.edit.failed")) : tr("partner.edit.failed"));
    }
  }

  function remove() {
    if (!dish) return;
    Alert.alert(tr("partner.edit.delete_title", { name: dish.name }), tr("partner.edit.delete_body"), [
      { text: tr("partner.edit.keep"), style: "cancel" },
      { text: tr("partner.edit.delete"), style: "destructive", onPress: async () => {
        try {
          unwrap(await api.core.DELETE("/api/v1/restaurants/{restaurant_id}/menu-items/{item_id}", { params: { path: { restaurant_id: rid, item_id: dish.id } } }));
          await onSaved();
        } catch (e) {
          setMsg(e instanceof ApiError ? errorMessage(e.body, tr("partner.edit.failed")) : tr("partner.edit.failed"));
        }
      } }]);
  }

  return (
    <Sheet testID="dish-editor" title={dish ? tr("partner.edit.edit_title", { name: dish.name }) : tr("partner.edit.new_title")} onClose={onClose} msg={msg}
      footer={<>
        {dish ? <Btn testID="dish-history" title={tr("partner.edit.history")} onPress={() => onHistory(dish)} /> : null}
        {dish ? <Btn testID="dish-delete" title={tr("partner.edit.delete")} kind="danger" onPress={remove} /> : null}
        <Btn testID="dish-save" title={tr("partner.edit.save")} kind="primary" height={56} busy={busy} onPress={() => void save()} />
      </>}>
      <Field label={tr("partner.edit.name")}>
        <TextInput testID="dish-name" disableFullscreenUI accessibilityLabel={tr("partner.edit.name")} value={name} onChangeText={setName} maxLength={255} style={s.input} />
      </Field>
      <Field label={tr("partner.edit.description")}>
        <TextInput testID="dish-description" disableFullscreenUI accessibilityLabel={tr("partner.edit.description")} value={description} onChangeText={setDescription}
          multiline maxLength={1000} style={[s.input, { minHeight: 72, textAlignVertical: "top" }]} />
      </Field>
      <Field label={tr("partner.edit.price", { currency: data.currency })}>
        <TextInput testID="dish-price" disableFullscreenUI accessibilityLabel={tr("partner.edit.price", { currency: data.currency })} value={price} onChangeText={setPrice}
          keyboardType={data.whole_units ? "number-pad" : "decimal-pad"} style={[s.input, num, { width: 180 }]} />
      </Field>
      {dish ? (
        <Field label={tr("partner.edit.photo")}>
          <Btn testID="edit-photo" title={dish.image_url ? tr("partner.photo.has_photo") : tr("partner.photo.add_photo")} onPress={() => onPhoto(dish)} />
        </Field>
      ) : null}
      <Field label={tr("partner.edit.category")}>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
          {data.categories.map((c, i) => {
            const on = c.id === categoryId;
            return (
              <Pressable key={c.id} testID={`dish-category-${i}`} accessibilityRole="radio" accessibilityState={{ checked: on }} onPress={() => setCategoryId(c.id)}
                style={[s.chip, on && { backgroundColor: color.kohl, borderColor: color.kohl }]}>
                <Text style={[type.label, { color: on ? color.white : color.kohl }]}>{c.name}{c.is_active ? "" : ` · ${tr("partner.edit.hidden")}`}</Text>
              </Pressable>
            );
          })}
        </View>
      </Field>
      {vegMarks ? (
        <Field label={tr("partner.edit.food_type")}>
          <Segmented label={tr("partner.edit.food_type")} value={veg ? "veg" : "non"} onChange={(v) => setVeg(v === "veg")}
            options={[{ value: "veg", label: tr("partner.edit.veg") }, { value: "non", label: tr("partner.edit.non_veg") }]} />
        </Field>
      ) : null}
      <Field label={tr("partner.edit.spice")}>
        <Segmented label={tr("partner.edit.spice")} value={spice} onChange={setSpice}
          options={[0, 1, 2, 3].map((n) => ({ value: n, label: tr(`partner.edit.spice_${n}`) }))} />
      </Field>
      <View style={{ gap: 4 }}>
        <Toggle testID="dish-available" on={onMenu} label={tr("partner.edit.available")} onPress={() => setOnMenu(!onMenu)} />
        <Text style={t.muted}>{tr("partner.edit.available_note")}</Text>
        {dish ? <Toggle testID="dish-sold-out" on={soldOut} label={tr("partner.edit.sold_out")} onPress={() => setSoldOut(!soldOut)} /> : null}
      </View>
      <Field label={tr("partner.edit.schedule")}>
        <Segmented label={tr("partner.edit.schedule")} value={timed} onChange={setTimed}
          options={[{ value: "all", label: tr("partner.edit.all_day") }, { value: "set", label: tr("partner.edit.set_hours") }]} />
        {timed === "set" ? (
          <View style={{ flexDirection: "row", gap: 12, alignItems: "center" }}>
            <TextInput testID="dish-from" disableFullscreenUI accessibilityLabel={tr("partner.edit.from")} value={from} onChangeText={setFrom} maxLength={5} style={[s.input, num, { width: 110 }]} />
            <Text style={t.body}>–</Text>
            <TextInput testID="dish-until" disableFullscreenUI accessibilityLabel={tr("partner.edit.until")} value={until} onChangeText={setUntil} maxLength={5} style={[s.input, num, { width: 110 }]} />
          </View>
        ) : null}
        <Text style={t.muted}>{tr("partner.edit.schedule_note")}</Text>
      </Field>
      <Field label={tr("partner.edit.options")}>
        <Text style={t.muted}>{tr("partner.edit.options_note")}</Text>
        {allGroups.map((g, i) => {
          const on = groups.includes(g.id);
          return (
            <View key={g.id} style={s.row}>
              <Pressable testID={`option-group-${i}`} accessibilityRole="checkbox" accessibilityState={{ checked: on }}
                onPress={() => setGroups(on ? groups.filter((x) => x !== g.id) : [...groups, g.id])} style={{ flexDirection: "row", gap: 10, alignItems: "center", flex: 1, minHeight: 44 }}>
                <View style={[s.box, on && { backgroundColor: color.peacock, borderColor: color.peacock }]}>{on ? <Text style={{ color: color.white }}>✓</Text> : null}</View>
                <View style={{ flex: 1 }}>
                  <Text style={type.label}>{g.name} · {g.min_picks > 0 ? tr("partner.edit.required") : tr("partner.edit.optional")} · {g.min_picks}–{g.max_picks}</Text>
                  <Text style={t.muted} numberOfLines={2}>{g.options.map((o) => `${o.name}${Number(o.price) > 0 ? ` +${cash(o.price, data.currency)}` : ""}`).join(", ")}</Text>
                </View>
              </Pressable>
              <Btn testID={`edit-group-${i}`} title={tr("partner.edit.edit_group")} onPress={() => setGroup(g)} />
            </View>
          );
        })}
        <Btn testID="new-group" title={tr("partner.edit.new_group")} onPress={() => setGroup("new")} />
      </Field>
      {group ? (
        <GroupEditor data={data} group={group === "new" ? null : group} onClose={() => setGroup(null)}
          onSaved={(g, deleted) => {
            setGroup(null);
            setAllGroups((was) => deleted ? was.filter((x) => x.id !== g.id) : was.some((x) => x.id === g.id) ? was.map((x) => (x.id === g.id ? g : x)) : [...was, g]);
            if (deleted) setGroups((was) => was.filter((x) => x !== g.id));
            else if (!groups.includes(g.id)) setGroups((was) => [...was, g.id]);
          }} />
      ) : null}
    </Sheet>
  );
}

// ── an option group ──────────────────────────────────────────────────────────

function GroupEditor({ data, group, onClose, onSaved }: {
  data: Manage; group: ManageGroup | null; onClose: () => void; onSaved: (g: ManageGroup, deleted?: boolean) => void;
}) {
  const { tr } = useTr();
  const rid = data.restaurant_id;
  const [name, setName] = useState(group?.name ?? "");
  const [min, setMin] = useState(group?.min_picks ?? 0);
  const [max, setMax] = useState(group?.max_picks ?? 1);
  const [options, setOptions] = useState<ManageOption[]>(group?.options.map((o) => ({ ...o, price: data.whole_units ? String(Math.round(Number(o.price))) : o.price }))
    ?? [{ name: "", price: "0", is_default: false, is_available: true }]);
  const [busy, setBusy] = useState(false);
  const set = (i: number, patch: Partial<ManageOption>) => setOptions(options.map((o, n) => (n === i ? { ...o, ...patch } : o)));

  const problem = !name.trim() ? tr("partner.edit.name_required")
    : options.some((o) => !o.name.trim()) ? tr("partner.edit.option_name_required")
    : options.map((o) => priceProblem(o.price, data.whole_units, tr, true)).find(Boolean)
    ?? (min > max || min > options.length ? tr("partner.edit.group_rule") : null);
  const { msg, setServer: setMsg, check } = useFormMsg(problem, [name, min, max, options]);

  async function save() {
    if (check()) return;
    setBusy(true);
    setMsg(null);
    const body = { name: name.trim(), min_picks: min, max_picks: max,
      options: options.map((o) => ({ ...(o.id ? { id: o.id } : {}), name: o.name.trim(), price: o.price.trim().replace(",", "."), is_default: o.is_default, is_available: o.is_available })) };
    try {
      const g = group
        ? unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/option-groups/{group_id}", { params: { path: { restaurant_id: rid, group_id: group.id } }, body }))
        : unwrap(await api.core.POST("/api/v1/restaurants/{restaurant_id}/option-groups", { ...r(rid), body }));
      onSaved(g as unknown as ManageGroup);
    } catch (e) {
      setBusy(false);
      setMsg(e instanceof ApiError ? errorMessage(e.body, tr("partner.edit.failed")) : tr("partner.edit.failed"));
    }
  }

  async function remove() {
    if (!group) return;
    try {
      unwrap(await api.core.DELETE("/api/v1/restaurants/{restaurant_id}/option-groups/{group_id}", { params: { path: { restaurant_id: rid, group_id: group.id } } }));
      onSaved(group, true);
    } catch (e) {
      setMsg(e instanceof ApiError ? errorMessage(e.body, tr("partner.edit.failed")) : tr("partner.edit.failed"));
    }
  }

  const step = (v: number, d: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v + d));
  return (
    <Sheet testID="group-editor" title={group ? tr("partner.edit.group_title", { name: group.name }) : tr("partner.edit.group_title_new")} onClose={onClose} msg={msg}
      footer={<>
        {group ? <Btn testID="group-delete" title={tr("partner.edit.delete_group")} kind="danger" onPress={() => void remove()} /> : null}
        <Btn testID="group-save" title={tr("partner.edit.save")} kind="primary" height={56} busy={busy} onPress={() => void save()} />
      </>}>
      <Field label={tr("partner.edit.group_name")}>
        <TextInput testID="group-name" disableFullscreenUI accessibilityLabel={tr("partner.edit.group_name")} value={name} onChangeText={setName} maxLength={80} style={s.input} />
      </Field>
      <Segmented label={tr("partner.edit.choice")} value={min > 0 ? "req" : "opt"} onChange={(v) => setMin(v === "req" ? Math.max(1, min) : 0)}
        options={[{ value: "req", label: tr("partner.edit.required") }, { value: "opt", label: tr("partner.edit.optional") }]} />
      <View style={{ flexDirection: "row", gap: 24, flexWrap: "wrap" }}>
        {([["min", min, setMin, 0], ["max", max, setMax, 1]] as const).map(([k, v, setV, lo]) => (
          <View key={k} style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
            <Text style={t.label}>{tr(`partner.edit.${k}`)}</Text>
            <Btn testID={`group-${k}-less`} title="−" label={tr(`partner.edit.${k}_less`)} onPress={() => setV(step(v, -1, lo, 20))} />
            <Text testID={`group-${k}`} style={[type.h3, num, { minWidth: 24, textAlign: "center" }]}>{v}</Text>
            <Btn testID={`group-${k}-more`} title="+" label={tr(`partner.edit.${k}_more`)} onPress={() => setV(step(v, 1, lo, 20))} />
          </View>
        ))}
      </View>
      {options.map((o, i) => (
        <View key={o.id ?? `new-${i}`} style={[s.row, { flexWrap: "wrap" }]}>
          <TextInput testID={`option-name-${i}`} disableFullscreenUI accessibilityLabel={`${tr("partner.edit.option_name")} ${i + 1}`} placeholder={tr("partner.edit.option_name")}
            value={o.name} onChangeText={(v) => set(i, { name: v })} maxLength={80} style={[s.input, { flex: 1, minWidth: 160 }]} />
          <TextInput testID={`option-price-${i}`} disableFullscreenUI accessibilityLabel={`${tr("partner.edit.option_price")} ${i + 1}`}
            value={o.price} onChangeText={(v) => set(i, { price: v })} keyboardType={data.whole_units ? "number-pad" : "decimal-pad"} style={[s.input, num, { width: 110 }]} />
          <Toggle on={o.is_available} label={tr("partner.edit.option_on")} onPress={() => set(i, { is_available: !o.is_available })} />
          {options.length > 1 ? <Btn title={tr("partner.edit.remove")} kind="danger" onPress={() => setOptions(options.filter((_, n) => n !== i))} /> : null}
        </View>
      ))}
      <Btn testID="add-option" title={tr("partner.edit.add_option")} onPress={() => setOptions([...options, { name: "", price: "0", is_default: false, is_available: true }])} />
    </Sheet>
  );
}

// ── categories ────────────────────────────────────────────────────────────────

const ROW = 64;

export function CategoriesEditor({ data, onClose, onChanged }: { data: Manage; onClose: () => void; onChanged: () => Promise<void> }) {
  const { tr } = useTr();
  const rid = data.restaurant_id;
  const [cats, setCats] = useState(data.categories);
  const [names, setNames] = useState<Record<string, string>>({});
  const [adding, setAdding] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [drag, setDrag] = useState<{ id: string; dy: Animated.Value } | null>(null);
  const [seen, setSeen] = useState(data.categories);
  if (seen !== data.categories) { // reloaded after a change: the server's order and names
    setSeen(data.categories);
    setCats(data.categories);
  }

  async function call(f: () => Promise<unknown>) {
    setMsg(null);
    try {
      await f();
      await onChanged();
    } catch (e) {
      setMsg(e instanceof ApiError ? errorMessage(e.body, tr("partner.edit.failed")) : tr("partner.edit.failed"));
    }
  }
  const put = (c: ManageCategory, body: Record<string, unknown>) => call(async () =>
    unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/categories/{category_id}", { params: { path: { restaurant_id: rid, category_id: c.id } }, body })));

  async function move(from: number, to: number) {
    if (to < 0 || to >= cats.length || to === from) return;
    const next = [...cats];
    const [c] = next.splice(from, 1);
    next.splice(to, 0, c!);
    setCats(next);
    await call(async () => unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/categories-order", { ...r(rid), body: { category_ids: next.map((x) => x.id) } })));
  }

  return (
    <Sheet testID="categories-editor" title={tr("partner.edit.categories_title")} onClose={onClose} msg={msg}>
      <Text style={t.muted}>{tr("partner.edit.categories_note")}</Text>
      <View>
        {cats.map((c, i) => (
          <CategoryRow key={c.id} c={c} i={i} count={cats.length} dragging={drag?.id === c.id} dy={drag?.id === c.id ? drag.dy : null}
            name={names[c.id] ?? c.name} onName={(v) => setNames({ ...names, [c.id]: v })}
            onRename={() => (names[c.id] ?? c.name).trim() && (names[c.id] ?? c.name).trim() !== c.name ? void put(c, { name: (names[c.id] ?? c.name).trim() }) : undefined}
            onToggle={() => void put(c, { is_active: !c.is_active })}
            onSchedule={(f, u) => void put(c, { available_from: f, available_until: u })}
            onDragStart={(dy) => setDrag({ id: c.id, dy })}
            onDragEnd={(steps) => { setDrag(null); void move(i, Math.max(0, Math.min(cats.length - 1, i + steps))); }}
            onMove={(d) => void move(i, i + d)} />
        ))}
      </View>
      <View style={s.row}>
        <TextInput testID="new-category" disableFullscreenUI accessibilityLabel={tr("partner.edit.new_category")} placeholder={tr("partner.edit.new_category")}
          value={adding} onChangeText={setAdding} maxLength={100} style={[s.input, { flex: 1 }]} />
        <Btn testID="add-category" title={tr("partner.edit.add")} kind="primary" disabled={!adding.trim()} onPress={() => void call(async () => {
          unwrap(await api.core.POST("/api/v1/restaurants/{restaurant_id}/categories", { ...r(rid), body: { name: adding.trim() } }));
          setAdding("");
        })} />
      </View>
    </Sheet>
  );
}

function CategoryRow({ c, i, count, dragging, dy, name, onName, onRename, onToggle, onSchedule, onDragStart, onDragEnd, onMove }: {
  c: ManageCategory; i: number; count: number; dragging: boolean; dy: Animated.Value | null; name: string; onName: (v: string) => void;
  onRename: () => void; onToggle: () => void; onSchedule: (from: string | null, until: string | null) => void;
  onDragStart: (dy: Animated.Value) => void; onDragEnd: (steps: number) => void; onMove: (d: number) => void;
}) {
  const { tr } = useTr();
  const [from, setFrom] = useState(c.available_from ?? "");
  const [until, setUntil] = useState(c.available_until ?? "");
  const [value] = useState(() => new Animated.Value(0));
  // Drag the ☰ handle up or down: the row follows the finger; let go and it lands that many rows away.
  const pan = useMemo(() => PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => true,
    onPanResponderTerminationRequest: () => false,
    onPanResponderGrant: () => { value.setValue(0); onDragStart(value); },
    onPanResponderMove: (_, g) => value.setValue(g.dy),
    onPanResponderRelease: (_, g) => { value.setValue(0); onDragEnd(Math.round(g.dy / ROW)); },
    onPanResponderTerminate: () => { value.setValue(0); onDragEnd(0); },
  }), [value, onDragStart, onDragEnd]);
  const timesOk = (!from && !until) || (okTime(from) && okTime(until) && from !== until);
  return (
    <Animated.View testID={`category-row-${i}`} style={[s.catRow, dragging && dy ? { transform: [{ translateY: dy }], zIndex: 2, elevation: 4, backgroundColor: color.white } : null]}>
      <View {...pan.panHandlers} testID={`category-drag-${i}`} accessible accessibilityRole="adjustable" accessibilityLabel={tr("partner.edit.drag", { name: c.name })}
        accessibilityActions={[{ name: "increment", label: tr("partner.edit.move_down", { name: c.name }) }, { name: "decrement", label: tr("partner.edit.move_up", { name: c.name }) }]}
        onAccessibilityAction={(e) => onMove(e.nativeEvent.actionName === "increment" ? 1 : -1)} style={s.handle}>
        <Text style={[type.h3, { color: color.muted }]}>☰</Text>
      </View>
      <View style={{ flex: 1, gap: 8 }}>
        <View style={s.row}>
          <TextInput testID={`category-name-${i}`} disableFullscreenUI accessibilityLabel={tr("partner.edit.rename")} value={name} onChangeText={onName}
            onBlur={onRename} onSubmitEditing={onRename} maxLength={100} style={[s.input, { flex: 1 }]} />
          <Btn testID={`category-rename-${i}`} title={tr("partner.edit.save")} disabled={!name.trim() || name.trim() === c.name} onPress={onRename} />
          <Toggle testID={`category-shown-${i}`} on={c.is_active} label={c.is_active ? tr("partner.edit.shown") : tr("partner.edit.hidden")} onPress={onToggle} />
        </View>
        <View style={[s.row, { flexWrap: "wrap" }]}>
          <Text style={t.muted}>{tr("partner.edit.schedule")}</Text>
          <TextInput testID={`category-from-${i}`} disableFullscreenUI accessibilityLabel={`${c.name} ${tr("partner.edit.from")}`} placeholder="07:00" value={from} onChangeText={setFrom} maxLength={5} style={[s.input, num, { width: 96 }]} />
          <Text style={t.body}>–</Text>
          <TextInput testID={`category-until-${i}`} disableFullscreenUI accessibilityLabel={`${c.name} ${tr("partner.edit.until")}`} placeholder="11:00" value={until} onChangeText={setUntil} maxLength={5} style={[s.input, num, { width: 96 }]} />
          <Btn testID={`category-hours-${i}`} title={from || until ? tr("partner.edit.set_hours") : tr("partner.edit.all_day")} disabled={!timesOk}
            onPress={() => onSchedule(from.trim() || null, until.trim() || null)} />
          {i > 0 ? <Btn testID={`category-up-${i}`} title="↑" label={tr("partner.edit.move_up", { name: c.name })} onPress={() => onMove(-1)} /> : null}
          {i < count - 1 ? <Btn testID={`category-down-${i}`} title="↓" label={tr("partner.edit.move_down", { name: c.name })} onPress={() => onMove(1)} /> : null}
        </View>
      </View>
    </Animated.View>
  );
}

// ── history ───────────────────────────────────────────────────────────────────

export function HistorySheet({ rid, currency, item, onClose }: { rid: string; currency: string; item: { id: string; name: string } | null; onClose: () => void }) {
  const { tr } = useTr();
  const { date } = useFormat();
  const { cash } = useFormat();
  const { time } = useI18n();
  const [rows, setRows] = useState<Change[] | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const page = (before?: string) => api.core.GET("/api/v1/restaurants/{restaurant_id}/menu/history", {
    params: { path: { restaurant_id: rid }, query: { limit: 30, ...(before ? { before } : {}), ...(item ? { item_id: item.id } : {}) } } })
    .then((x) => unwrap(x) as unknown as { changes: Change[]; next: string | null });
  const failed = (e: unknown) => setMsg(e instanceof ApiError ? errorMessage(e.body, tr("partner.edit.failed")) : tr("partner.edit.failed"));
  function load(before?: string) {
    page(before).then((res) => { setRows((was) => [...(before ? was ?? [] : []), ...res.changes]); setNext(res.next); }).catch(failed);
  }
  useEffect(() => {
    let live = true;
    page().then((res) => { if (live) { setRows(res.changes); setNext(res.next); } }).catch((e: unknown) => { if (live) failed(e); });
    return () => { live = false; };
  }, [rid, item?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const value = (field: string, v: unknown): string => {
    if (v === null || v === undefined || v === "") return "—";
    if (typeof v === "boolean") return v ? tr("partner.edit.yes") : tr("partner.edit.no");
    if (field === "price") return cash(String(v), currency);
    if (field === "spice_level") return tr(`partner.edit.spice_${Number(v)}`);
    if (field === "image_url") return tr("partner.photo.photo");
    return String(v);
  };
  return (
    <Sheet testID="menu-history" title={item ? tr("partner.edit.history_dish", { name: item.name }) : tr("partner.edit.history_title")} onClose={onClose} msg={msg}>
      {rows === null && !msg ? <ActivityIndicator color={color.peacock} /> : null}
      {rows?.length === 0 ? <Text style={t.muted}>{tr("partner.edit.history_none")}</Text> : null}
      {(rows ?? []).map((c, n) => (
        <View key={c.id} testID={`history-${n}`} style={s.hist}>
          <Text style={type.label}>
            {c.name} · {tr(`partner.edit.action_${c.action}`)}
          </Text>
          <Text style={[t.muted, num]}>
            {date(c.at)} {time(c.at)} · {c.who === "you" ? tr("partner.edit.who_you") : c.who === "bhojango" ? tr("partner.edit.who_bhojango") : c.who}
          </Text>
          {c.action !== "added" ? c.changes.map((x) => (
            <Text key={x.field} style={[t.body, num]}>
              {tr(`partner.edit.field_${x.field}`)}: {value(x.field, x.old)} → {value(x.field, x.new)}
            </Text>
          )) : null}
        </View>
      ))}
      {next ? <Btn testID="history-more" title={tr("partner.edit.history_more")} onPress={() => load(next)} /> : null}
    </Sheet>
  );
}

const s = StyleSheet.create({
  scrim: { flex: 1, backgroundColor: "rgba(17,20,24,0.45)", alignItems: "center", justifyContent: "center" },
  sheet: { backgroundColor: color.white, borderRadius: 24, padding: 28 },
  input: { borderWidth: 1.5, borderColor: color.lineStrong, borderRadius: 12, paddingHorizontal: 14, minHeight: 48, color: color.kohl, ...type.body },
  chip: { borderWidth: 1.5, borderColor: color.lineStrong, borderRadius: 999, paddingHorizontal: 14, minHeight: 40, justifyContent: "center" },
  row: { flexDirection: "row", alignItems: "center", gap: 10 },
  box: { width: 26, height: 26, borderRadius: 6, borderWidth: 2, borderColor: color.lineStrong, alignItems: "center", justifyContent: "center" },
  switch: { width: 46, height: 26, borderRadius: 13, backgroundColor: "#C9D3D4" },
  knob: { position: "absolute", top: 3, left: 3, width: 20, height: 20, borderRadius: 10, backgroundColor: color.white },
  catRow: { flexDirection: "row", gap: 12, alignItems: "center", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: color.line, minHeight: ROW },
  handle: { width: 44, height: 56, alignItems: "center", justifyContent: "center" },
  hist: { gap: 2, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: color.line },
});

