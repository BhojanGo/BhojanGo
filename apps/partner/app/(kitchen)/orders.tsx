// PartnerOrders.html: New (ring, accept timer, "ready in" picker), Preparing
// (time left, almost ready, mark ready), Ready for pickup (rider on the way).
// The header carries the kitchen's rating (lib/ratings.tsx): the dashboard's summary.
// On a phone (portrait, lib/layout.ts) the three columns become tabs over one list,
// and tapping an order opens its detail (the same card); Back returns to the list.
// R27: a tablet held upright gets the same tabs, with the full cards in the list.
import { api, ApiError, LanguagePill, LoadError, loadErrorText, num, SafeAreaView, type Translate, type, unwrap, useI18n } from "@bhojango/mobile-core";
import { useEffect, useState } from "react";
import { Alert, BackHandler, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { COOKING, NEW, READY, useBoard } from "../../lib/board";
import { code, move, useFormat, reject, riderEta, useKitchen, type Order, type Today } from "../../lib/data";
import { useLayout } from "../../lib/layout";
import { RatingChip } from "../../lib/ratings";
import { Btn, Card, color, Count, Icon, radius, Segmented, t, textFont, tone } from "../../lib/ui";

const PREP = [15, 20, 25, 30];

function useNow(every = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), every);
    return () => clearInterval(id);
  }, [every]);
  return now;
}

type Item = { name?: string; quantity?: number; options?: string[] };

export default function Orders() {
  const kitchen = useKitchen((s) => s.kitchen)!;
  const { orders, today, failure, refresh, setToday } = useBoard();
  const [pausing, setPausing] = useState(false);
  const { t: tr } = useI18n();
  const { narrow, portrait } = useLayout();
  const fresh = orders.filter((o) => NEW.includes(o.status)).sort((a, b) => a.created_at.localeCompare(b.created_at));
  const cooking = orders.filter((o) => COOKING.includes(o.status));
  const ready = orders.filter((o) => READY.includes(o.status));

  async function act(fn: () => Promise<unknown>) {
    try {
      await fn();
    } catch (e) {
      Alert.alert(tr("partner.orders.failed"), e instanceof ApiError ? e.message : loadErrorText(e, tr).reason);
    }
    await refresh(kitchen.id);
  }

  async function busy() {
    const on = !(today && today.busy_extra_minutes > 0);
    await act(async () => setToday(unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/busy", {
      params: { path: { restaurant_id: kitchen.id } }, body: { extra_minutes: on ? 10 : 0 } }))));
  }

  async function pause(minutes: number | null, paused = true) {
    setPausing(false);
    await act(async () => setToday(unwrap(await api.core.PUT("/api/v1/restaurants/{restaurant_id}/pause", {
      params: { path: { restaurant_id: kitchen.id } }, body: { paused, minutes } }))));
  }

  return (
    <SafeAreaView testID="orders-screen" edges={["top", "right"]} style={{ flex: 1 }}>
      <Header today={today} onBusy={busy} onPause={() => (today?.paused ? pause(null, false) : setPausing(true))} />
      {/* R9: the first load failed: the error state and Retry; later polls that fail: one line over the board (it keeps polling). */}
      {failure && today ? (
        <Text testID="board-offline" accessibilityRole="alert" style={[t.muted, { color: color.chili, paddingHorizontal: 24, paddingTop: 8 }]}>
          {`${loadErrorText(failure, tr).title}. ${loadErrorText(failure, tr).reason}`}
        </Text>
      ) : null}
      {failure && !today ? (
        <View style={{ flex: 1, padding: 24 }}><LoadError error={failure} onRetry={() => refresh(kitchen.id)} fill /></View>
      ) : narrow || portrait ? (
        <TabBoard fresh={fresh} cooking={cooking} ready={ready} defaultPrep={today?.prep_minutes ?? 20} act={act} cards={!narrow} />
      ) : (
      <View style={s.board}>
        <Column testID="column-new" title={tr("partner.orders.new")} count={fresh.length} badge={[color.peacock, color.white]}>
          {fresh.length === 0 ? <Text style={t.muted}>{tr("partner.orders.new_empty")}</Text> : null}
          {fresh.map((o, i) => <NewCard key={o.id} order={o} first={i === 0} defaultPrep={today?.prep_minutes ?? 20} act={act} />)}
        </Column>
        <Column testID="column-preparing" title={tr("partner.orders.preparing")} count={cooking.length} badge={[tone.kesarSoft, tone.kesarInk]}>
          {cooking.map((o) => <CookingCard key={o.id} order={o} act={act} />)}
        </Column>
        <Column testID="column-ready" title={tr("partner.orders.ready")} count={ready.length} badge={[color.peacockTint, color.peacockDeep]}>
          {ready.map((o) => <ReadyCard key={o.id} order={o} />)}
          <Text style={[t.muted, { textAlign: "center", marginTop: 4 }]}>{tr("partner.orders.ready_note")}</Text>
        </Column>
      </View>
      )}
      <Modal visible={pausing} transparent animationType="fade" supportedOrientations={["landscape", "portrait"]} onRequestClose={() => setPausing(false)}>
        <Pressable style={s.scrim} onPress={() => setPausing(false)}>
          <View style={[s.sheet, narrow && { padding: 24 }]} accessibilityLabel={tr("partner.orders.pause_title")}>
            <Text style={t.h1}>{tr("partner.orders.pause_title")}</Text>
            <Text style={t.muted}>{tr("partner.orders.pause_sub")}</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 12 }}>
              {[15, 30, 60].map((m) => <Btn key={m} title={tr("partner.orders.minutes", { min: m })} grow onPress={() => pause(m)} />)}
              <Btn title={tr("partner.orders.until_resume")} grow kind="dark" onPress={() => pause(null)} />
            </View>
          </View>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

function Header({ today, onBusy, onPause }: { today: Today | null; onBusy: () => void; onPause: () => void }) {
  const { cash, clock } = useFormat();
  const { t: tr } = useI18n();
  const { width, narrow: phone, portrait } = useLayout();
  const compact = width < 1100; // a phone, or a small tablet
  // A phone, or a tablet upright (R27): the name on one line, the status and the buttons below.
  const narrow = phone || portrait;
  const kitchen = useKitchen((s) => s.kitchen)!;
  const cur = today?.currency ?? kitchen.currency;
  const open = today && today.open_now && !today.paused;
  const closes = today?.closes_at ? clock(`2000-01-01T${today.closes_at}:00`) : null;
  const status = !today ? "…" : today.paused
    ? today.paused_until ? tr("partner.orders.paused_till", { time: clock(today.paused_until, today.time_zone) }) : tr("partner.orders.paused")
    : open ? (closes ? tr("partner.orders.open_till", { time: closes }) : tr("partner.orders.open")) : today.reason ?? tr("partner.orders.closed");
  const title = (
    <View style={{ flex: 1, minWidth: 0 }}>
      <Text accessibilityRole="header" style={t.h1} numberOfLines={1}>{today?.name ?? kitchen.name}</Text>
      <Text style={[t.muted, { marginTop: 2 }]} numberOfLines={phone ? 2 : undefined}>
        {[today?.area, today ? tr("partner.orders.today_orders", { count: today.today_orders }) : null, today ? cash(today.today_sales, cur) : null]
          .filter(Boolean).join(" · ")}
      </Text>
    </View>
  );
  const chip = <RatingChip kitchenId={kitchen.id} />;
  const pill = <LanguagePill />; // the kitchen's country's languages (the account's country, Markets locales)
  const controls = (
    <>
      <View testID="kitchen-status" style={[s.status, !open && { backgroundColor: tone.kesarSoft }, narrow && { flexGrow: 1, flexShrink: 1, height: phone ? 44 : 48 }]}
        accessibilityLabel={status}>
        <View style={[s.dot, { backgroundColor: open ? color.peacock : tone.kesarInk }]} />
        <Text style={[type.label, { color: open ? color.peacockDeep : tone.kesarInk, flexShrink: 1 }]} numberOfLines={1}>{status}</Text>
      </View>
      <Btn testID="busy" height={phone ? 44 : 48} style={phone && { paddingHorizontal: 14 }}
        title={today && today.busy_extra_minutes > 0 ? tr("partner.orders.busy_undo", { min: today.busy_extra_minutes })
          : compact ? tr("partner.orders.busy_short") : tr("partner.orders.busy")}
        label={today && today.busy_extra_minutes > 0 ? undefined : tr("partner.orders.busy")} onPress={onBusy} />
      <Btn testID="pause" height={phone ? 44 : 48} style={phone && { paddingHorizontal: 14 }}
        title={today?.paused ? tr("partner.orders.resume") : compact ? tr("partner.orders.pause_short") : tr("partner.orders.pause")}
        label={today?.paused ? undefined : tr("partner.orders.pause")} kind={today?.paused ? "dark" : "outline"} onPress={onPause} />
    </>
  );
  // A phone's width: the name and the rating on one line, the status and the buttons below.
  if (narrow) {
    return (
      <View style={[s.header, s.headerNarrow, !phone && { paddingHorizontal: 24 }]}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>{title}{chip}{pill}</View>
        <View style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 }}>{controls}</View>
      </View>
    );
  }
  return (
    <View style={s.header}>
      {title}
      {chip}
      {controls}
      {pill}
    </View>
  );
}

function Column({ title, count, badge, children, testID }: { title: string; count: number; badge: [string, string]; children: React.ReactNode; testID?: string }) {
  return (
    <View testID={testID} style={s.col} accessibilityLabel={title}>
      <View style={s.colHead}>
        <Text style={type.label}>{title}</Text>
        <Count n={count} bg={badge[0]} fg={badge[1]} />
      </View>
      <ScrollView contentContainerStyle={{ gap: 12, paddingBottom: 24 }} showsVerticalScrollIndicator={false}>{children}</ScrollView>
    </View>
  );
}

type Tab = "new" | "preparing" | "ready";
type Act = (fn: () => Promise<unknown>) => Promise<void>;

/**
 * The board on a phone: New / Preparing / Ready as tabs (the same testIDs as the
 * tablet's columns), one list of orders, and an order's detail (its full card:
 * accept, ready in, mark ready, the rider) with Back, or the phone's back button.
 * `cards` (a tablet upright, R27): the same tabs, and the list shows each order's full
 * card (accept / mark ready right there), as the landscape columns do.
 */
function TabBoard({ fresh, cooking, ready, defaultPrep, act, cards = false }: {
  fresh: Order[]; cooking: Order[]; ready: Order[]; defaultPrep: number; act: Act; cards?: boolean;
}) {
  const { t: tr } = useI18n();
  const [tab, setTab] = useState<Tab>("new");
  const [openId, setOpenId] = useState<string | null>(null);
  // Picked up (or cancelled) while open: it leaves the board, and the list shows again.
  const open = openId ? [...fresh, ...cooking, ...ready].find((o) => o.id === openId) ?? null : null;
  const shown = open?.id;
  useEffect(() => {
    if (!shown) return;
    const sub = BackHandler.addEventListener("hardwareBackPress", () => {
      setOpenId(null);
      return true;
    });
    return () => sub.remove();
  }, [shown]);

  if (open && !cards) {
    return (
      <ScrollView testID="order-detail" contentContainerStyle={{ padding: 16, gap: 12, paddingBottom: 32 }}>
        <Pressable testID="order-back" accessibilityRole="button" accessibilityLabel={tr("common.back")} onPress={() => setOpenId(null)}
          hitSlop={8} style={s.back}>
          <Icon name="back" size={20} />
          <Text style={type.label}>{tr("common.back")}</Text>
        </Pressable>
        {NEW.includes(open.status) ? <NewCard order={open} first defaultPrep={defaultPrep} act={act} />
          : COOKING.includes(open.status) ? <CookingCard order={open} act={act} /> : <ReadyCard order={open} />}
      </ScrollView>
    );
  }

  const tabs: { key: Tab; title: string; short: string; list: Order[]; badge: [string, string] }[] = [
    { key: "new", title: tr("partner.orders.new"), short: tr("partner.orders.new"), list: fresh, badge: [color.peacock, color.white] },
    { key: "preparing", title: tr("partner.orders.preparing"), short: tr("partner.orders.preparing"), list: cooking, badge: [tone.kesarSoft, tone.kesarInk] },
    { key: "ready", title: tr("partner.orders.ready"), short: cards ? tr("partner.orders.ready") : tr("partner.orders.ready_short"), list: ready, badge: [color.peacockTint, color.peacockDeep] },
  ];
  const current = tabs.find((x) => x.key === tab)!;
  return (
    <View style={{ flex: 1 }}>
      <View accessibilityRole="tablist" style={[s.tabs, cards && { paddingHorizontal: 24, paddingTop: 16, gap: 12 }]}>
        {tabs.map((x) => {
          const on = x.key === tab;
          // New orders waiting while another tab is open: the count turns red.
          const badge: [string, string] = x.key === "new" && !on && x.list.length > 0 ? [color.chili, color.white] : x.badge;
          return (
            <Pressable key={x.key} testID={`column-${x.key}`} accessibilityRole="tab" accessibilityState={{ selected: on }} accessibilityLabel={x.title}
              onPress={() => setTab(x.key)} style={[s.tab, cards && { height: 52 }, on && s.tabOn]}>
              <Text style={[type.label, { color: on ? color.kohl : color.muted, flexShrink: 1 }]} numberOfLines={1}>{x.short}</Text>
              <Count n={x.list.length} bg={badge[0]} fg={badge[1]} />
            </Pressable>
          );
        })}
      </View>
      <ScrollView testID="order-list" contentContainerStyle={cards ? { padding: 24, gap: 12, paddingBottom: 32 } : { padding: 16, gap: 10, paddingBottom: 24 }}>
        {tab === "new" && fresh.length === 0 ? <Text style={t.muted}>{tr("partner.orders.new_empty")}</Text> : null}
        {cards ? current.list.map((o, i) => (
          tab === "new" ? <NewCard key={o.id} order={o} first={i === 0} defaultPrep={defaultPrep} act={act} />
            : tab === "preparing" ? <CookingCard key={o.id} order={o} act={act} /> : <ReadyCard key={o.id} order={o} />
        )) : current.list.map((o, i) => <OrderRow key={o.id} order={o} index={i} onOpen={() => setOpenId(o.id)} />)}
        {tab === "ready" ? <Text style={[t.muted, { textAlign: "center", marginTop: 4 }]}>{tr("partner.orders.ready_note")}</Text> : null}
      </ScrollView>
    </View>
  );
}

/** One order in the phone's list: code, customer, the items, and its clock (to accept, left, ready at). */
function OrderRow({ order: o, index, onOpen }: { order: Order; index: number; onOpen: () => void }) {
  const { clock } = useFormat();
  const { t: tr } = useI18n();
  const fresh = NEW.includes(o.status);
  const now = useNow(fresh ? 1000 : 15000);
  const items = (o.items ?? []) as Item[];
  const who = `${code(o.id)} · ${name(o, tr("partner.orders.customer"))}`;
  let when: string, tint: string;
  if (fresh) {
    const left = o.accept_due_at ? Math.max(0, Math.round((Date.parse(o.accept_due_at) - now) / 1000)) : null;
    when = left == null ? "" : `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
    tint = color.chili;
  } else if (COOKING.includes(o.status)) {
    when = cookingLabel(o, now, tr);
    tint = tone.kesarInk;
  } else {
    when = tr("partner.orders.ready_at", { time: clock(o.actual_ready_at) });
    tint = color.peacockDeep;
  }
  return (
    <Pressable testID={`order-row-${index}`} accessibilityRole="button" accessibilityLabel={tr("partner.orders.open_order", { order: who })} onPress={onOpen}
      style={({ pressed }) => [s.orderRow, fresh && index === 0 && { borderColor: color.peacock, borderWidth: 2 }, pressed && { opacity: 0.85 }]}>
      <View style={{ flex: 1, minWidth: 0, gap: 4 }}>
        <Text style={t.title} numberOfLines={1}>{who}</Text>
        <Text style={t.muted} numberOfLines={2}>{items.map((i) => `${i.quantity ?? 1}× ${i.name}`).join(" · ")}</Text>
      </View>
      <Text style={[fresh ? type.h3 : type.small, num, { color: tint }]}>{when}</Text>
      <Icon name="chevron" size={18} stroke={color.muted} />
    </Pressable>
  );
}

/** "12 min left", "3 min late" or "almost ready": a cooking order's clock. */
function cookingLabel(o: Order, now: number, tr: Translate) {
  if (o.status === "almost_ready") return tr("partner.orders.almost_ready_label");
  const start = o.restaurant_accepted_at ? Date.parse(o.restaurant_accepted_at) : now;
  const left = Math.round((start + (o.estimated_prep_minutes ?? 20) * 60000 - now) / 60000);
  return left < 0 ? tr("partner.orders.late", { min: -left }) : tr("partner.orders.left", { min: left });
}

function name(o: Order, customer: string) {
  return (o.customer as { name?: string } | null)?.name ?? customer;
}

function NewCard({ order: o, first, defaultPrep, act }: { order: Order; first: boolean; defaultPrep: number; act: Act }) {
  const { cash, clock } = useFormat();
  const { t: tr } = useI18n();
  const now = useNow();
  const [prep, setPrep] = useState(() => PREP.reduce((a, b) => (Math.abs(b - defaultPrep) < Math.abs(a - defaultPrep) ? b : a)));
  const [busy, setBusy] = useState<string | null>(null);
  const left = o.accept_due_at ? Math.max(0, Math.round((Date.parse(o.accept_due_at) - now) / 1000)) : null;
  const items = (o.items ?? []) as Item[];
  const run = (k: string, fn: () => Promise<unknown>) => async () => {
    setBusy(k);
    await act(fn);
    setBusy(null);
  };
  return (
    <Card highlight={first}>
      <View style={s.row}>
        <View>
          <Text style={type.h3}>{code(o.id)} · {name(o, tr("partner.orders.customer"))}</Text>
          <Text style={[t.muted, { marginTop: 2 }]}>{tr("partner.orders.delivery_paid", { time: clock(o.placed_at ?? o.created_at, o.time_zone) })}</Text>
        </View>
        {left != null ? (
          <View style={{ alignItems: "flex-end" }} accessibilityLabel={tr("partner.orders.left_to_accept", { min: Math.floor(left / 60), sec: left % 60 })}>
            <Text style={[type.h3, num, { color: color.chili }]}>
              {Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")}
            </Text>
            <Text style={[type.caption, { color: color.muted }]}>{tr("partner.orders.to_accept")}</Text>
          </View>
        ) : null}
      </View>
      <View style={{ gap: 8 }}>
        {items.map((it, i) => (
          <View key={i}>
            <Text style={t.body}><Text style={textFont("700")}>{it.quantity ?? 1}×</Text> {it.name}</Text>
            {it.options?.length ? <Text style={[t.muted, { marginTop: 2 }]}>{it.options.join(" · ")}</Text> : null}
          </View>
        ))}
        {o.special_instructions ? (
          <View style={s.note}><Text style={[type.small, { color: tone.kesarInk }]}>{tr("partner.orders.note", { note: o.special_instructions })}</Text></View>
        ) : null}
      </View>
      <View>
        <Text style={[t.label, { marginBottom: 8 }]}>{tr("partner.orders.ready_in")}</Text>
        <Segmented label={tr("partner.orders.ready_in")} value={prep} onChange={setPrep}
          options={PREP.map((m) => ({ value: m, label: m === prep ? tr("partner.orders.minutes", { min: m }) : String(m) }))} />
      </View>
      <View style={{ flexDirection: "row", gap: 12 }}>
        <Btn title={tr("partner.orders.reject")} kind="danger" height={56} busy={busy === "reject"}
          onPress={() => Alert.alert(tr("partner.orders.reject_title"), tr("partner.orders.reject_body"), [
            { text: tr("partner.orders.keep"), style: "cancel" }, { text: tr("partner.orders.reject"), style: "destructive", onPress: run("reject", () => reject(o.id)) }])} />
        <Btn testID={first ? "accept" : undefined} title={tr("partner.orders.accept", { amount: cash(o.subtotal, o.currency) })} kind="primary" height={56} grow
          busy={busy === "accept"} onPress={run("accept", async () => { await move(o.id, "accepted", prep); await move(o.id, "preparing"); })} />
      </View>
    </Card>
  );
}

function CookingCard({ order: o, act }: { order: Order; act: Act }) {
  const { t: tr } = useI18n();
  const now = useNow(15000);
  const start = o.restaurant_accepted_at ? Date.parse(o.restaurant_accepted_at) : now;
  const total = (o.estimated_prep_minutes ?? 20) * 60000;
  const left = Math.round((start + total - now) / 60000);
  const done = Math.min(1, Math.max(0, (now - start) / total));
  const items = (o.items ?? []) as Item[];
  const almost = o.status === "almost_ready";
  return (
    <Card>
      <View style={s.row}>
        <Text style={t.title}>{code(o.id)} · {name(o, tr("partner.orders.customer"))}</Text>
        <Text style={[type.label, { color: left < 0 ? color.chili : tone.kesarInk }]}>{cookingLabel(o, now, tr)}</Text>
      </View>
      <Text style={t.muted}>{items.map((i) => `${i.quantity ?? 1}× ${i.name}`).join(" · ")}</Text>
      <View style={s.track}><View style={[s.fill, { width: `${Math.round(done * 100)}%` }]} /></View>
      <View style={{ flexDirection: "row", gap: 8, marginTop: 4 }}>
        {!almost ? (
          <Btn title={tr("partner.orders.almost_ready")} onPress={() => act(async () => {
            if (o.status === "accepted") await move(o.id, "preparing");
            await move(o.id, "almost_ready");
          })} />
        ) : null}
        <Btn title={tr("partner.orders.mark_ready")} kind="dark" grow onPress={() => act(async () => {
          if (o.status === "accepted") await move(o.id, "preparing");
          await move(o.id, "ready");
        })} />
      </View>
    </Card>
  );
}

function ReadyCard({ order: o }: { order: Order }) {
  const { clock } = useFormat();
  const { t: tr } = useI18n();
  const [eta, setEta] = useState<number | null>(null);
  useEffect(() => {
    if (!o.driver_id) return;
    let live = true;
    const tick = () => riderEta(o.id).then((m) => live && setEta(m));
    void tick();
    const id = setInterval(tick, 15000);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, [o.id, o.driver_id]);
  const items = (o.items ?? []) as Item[];
  const n = items.reduce((a, i) => a + (i.quantity ?? 1), 0);
  const bags = Math.max(1, Math.ceil(n / 4));
  const rider = o.rider as { name?: string; first_name?: string } | null;
  const rname = rider?.name ?? rider?.first_name;
  return (
    <Card>
      <View style={s.row}>
        <Text style={t.title}>{code(o.id)} · {name(o, tr("partner.orders.customer"))}</Text>
        <Text style={[type.label, { color: color.peacockDeep }]}>{tr("partner.orders.ready_at", { time: clock(o.actual_ready_at, o.time_zone) })}</Text>
      </View>
      <Text style={t.muted}>{[...items.map((i) => `${i.quantity ?? 1}× ${i.name}`), tr("partner.orders.bags", { count: bags })].join(" · ")}</Text>
      <View style={s.rider}>
        <View style={s.avatar}><Text style={[type.label, { color: color.peacockDeep }]}>{rname ? rname.split(/\s+/).filter(Boolean).map((p) => [...p][0]).join("").slice(0, 2).toUpperCase() : "…"}</Text></View>
        <View style={{ flex: 1 }}>
          <Text style={type.label}>
            {rname ? `${rname} · ${eta == null ? tr("partner.orders.on_the_way") : eta <= 1 ? tr("partner.orders.arriving") : tr("partner.orders.min_away", { min: eta })}`
              : tr("partner.orders.finding_rider")}
          </Text>
          <Text style={t.muted}>{tr("partner.orders.order_code", { code: code(o.id) })}</Text>
        </View>
      </View>
    </Card>
  );
}

const s = StyleSheet.create({
  header: {
    minHeight: 80, paddingHorizontal: 24, paddingVertical: 8, backgroundColor: color.white, borderBottomWidth: 1, borderBottomColor: color.line,
    flexDirection: "row", alignItems: "center", gap: 16,
  },
  headerNarrow: { flexDirection: "column", alignItems: "stretch", paddingHorizontal: 16, paddingVertical: 12, gap: 10 },
  tabs: { flexDirection: "row", gap: 6, paddingHorizontal: 16, paddingTop: 12 },
  tab: { flex: 1, minWidth: 0, height: 44, borderRadius: radius.pill, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6,
    paddingHorizontal: 8, borderWidth: 1.5, borderColor: color.line, backgroundColor: color.white },
  tabOn: { borderColor: color.kohl },
  orderRow: { flexDirection: "row", alignItems: "center", gap: 12, padding: 16, borderRadius: radius.card, borderWidth: 1, borderColor: color.line,
    backgroundColor: color.white },
  back: { flexDirection: "row", alignItems: "center", gap: 6, alignSelf: "flex-start", height: 40 },
  status: { flexDirection: "row", alignItems: "center", gap: 8, height: 48, paddingHorizontal: 16, borderRadius: radius.pill, backgroundColor: color.peacockTint },
  dot: { width: 8, height: 8, borderRadius: 4 },
  board: { flex: 1, flexDirection: "row", padding: 24, gap: 16 },
  col: { flex: 1, minWidth: 0, gap: 12 },
  colHead: { height: 28, flexDirection: "row", alignItems: "center", gap: 8 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: 12 },
  note: { padding: 12, borderRadius: radius.chip, backgroundColor: tone.kesarSoft },
  track: { height: 6, borderRadius: 3, backgroundColor: color.divider },
  fill: { height: 6, borderRadius: 3, backgroundColor: color.kesar },
  rider: { flexDirection: "row", alignItems: "center", gap: 12, padding: 12, borderRadius: 12, backgroundColor: color.porcelain },
  avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: color.peacockTint, alignItems: "center", justifyContent: "center" },
  scrim: { flex: 1, backgroundColor: "rgba(17,20,24,0.4)", alignItems: "center", justifyContent: "center" },
  sheet: { width: 640, maxWidth: "92%", backgroundColor: color.white, borderRadius: radius.sheet, padding: 32, gap: 16 },
});
