// PartnerOrders.html: New (ring, accept timer, "ready in" picker), Preparing
// (time left, almost ready, mark ready), Ready for pickup (rider on the way).
// The header carries the kitchen's rating (lib/ratings.tsx): the dashboard's summary.
import { api, ApiError, unwrap, useI18n } from "@bhojango/mobile-core";
import { useEffect, useState } from "react";
import { Alert, Modal, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { COOKING, NEW, READY, useBoard } from "../../lib/board";
import { code, move, useFormat, reject, riderEta, useKitchen, type Order, type Today } from "../../lib/data";
import { RatingChip } from "../../lib/ratings";
import { Btn, Card, color, Count, radius, Segmented, t, textFont, tone } from "../../lib/ui";

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
  const { orders, today, error, refresh, setToday } = useBoard();
  const [pausing, setPausing] = useState(false);
  const { t: tr } = useI18n();
  const fresh = orders.filter((o) => NEW.includes(o.status)).sort((a, b) => a.created_at.localeCompare(b.created_at));
  const cooking = orders.filter((o) => COOKING.includes(o.status));
  const ready = orders.filter((o) => READY.includes(o.status));

  async function act(fn: () => Promise<unknown>) {
    try {
      await fn();
    } catch (e) {
      Alert.alert(tr("partner.orders.failed"), e instanceof ApiError ? e.message : (e as Error).message);
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
      {error ? <Text style={[t.muted, { color: color.chili, paddingHorizontal: 24, paddingTop: 8 }]}>{error}</Text> : null}
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
      <Modal visible={pausing} transparent animationType="fade" onRequestClose={() => setPausing(false)}>
        <Pressable style={s.scrim} onPress={() => setPausing(false)}>
          <View style={s.sheet} accessibilityLabel={tr("partner.orders.pause_title")}>
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
  const { width } = useWindowDimensions();
  const compact = width < 1100; // a phone held sideways, or a small tablet
  const kitchen = useKitchen((s) => s.kitchen)!;
  const cur = today?.currency ?? kitchen.currency;
  const open = today && today.open_now && !today.paused;
  const closes = today?.closes_at ? clock(`2000-01-01T${today.closes_at}:00`) : null;
  const status = !today ? "…" : today.paused
    ? today.paused_until ? tr("partner.orders.paused_till", { time: clock(today.paused_until) }) : tr("partner.orders.paused")
    : open ? (closes ? tr("partner.orders.open_till", { time: closes }) : tr("partner.orders.open")) : today.reason ?? tr("partner.orders.closed");
  return (
    <View style={s.header}>
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text accessibilityRole="header" style={t.h1} numberOfLines={1}>{today?.name ?? kitchen.name}</Text>
        <Text style={[t.muted, { marginTop: 2 }]}>
          {[today?.area, today ? tr("partner.orders.today_orders", { count: today.today_orders }) : null, today ? cash(today.today_sales, cur) : null]
            .filter(Boolean).join(" · ")}
        </Text>
      </View>
      <RatingChip kitchenId={kitchen.id} />
      <View testID="kitchen-status" style={[s.status, !open && { backgroundColor: tone.kesarSoft }]} accessibilityLabel={status}>
        <View style={[s.dot, { backgroundColor: open ? color.peacock : tone.kesarInk }]} />
        <Text style={[textFont("800"), { fontSize: 14, color: open ? color.peacockDeep : tone.kesarInk }]} numberOfLines={1}>{status}</Text>
      </View>
      <Btn testID="busy" title={today && today.busy_extra_minutes > 0 ? tr("partner.orders.busy_undo", { min: today.busy_extra_minutes })
        : compact ? tr("partner.orders.busy_short") : tr("partner.orders.busy")}
        label={today && today.busy_extra_minutes > 0 ? undefined : tr("partner.orders.busy")} onPress={onBusy} />
      <Btn testID="pause" title={today?.paused ? tr("partner.orders.resume") : compact ? tr("partner.orders.pause_short") : tr("partner.orders.pause")}
        label={today?.paused ? undefined : tr("partner.orders.pause")} kind={today?.paused ? "dark" : "outline"} onPress={onPause} />
    </View>
  );
}

function Column({ title, count, badge, children, testID }: { title: string; count: number; badge: [string, string]; children: React.ReactNode; testID?: string }) {
  return (
    <View testID={testID} style={s.col} accessibilityLabel={title}>
      <View style={s.colHead}>
        <Text style={[textFont("800"), { fontSize: 15 }]}>{title}</Text>
        <Count n={count} bg={badge[0]} fg={badge[1]} />
      </View>
      <ScrollView contentContainerStyle={{ gap: 12, paddingBottom: 24 }} showsVerticalScrollIndicator={false}>{children}</ScrollView>
    </View>
  );
}

function name(o: Order, customer: string) {
  return (o.customer as { name?: string } | null)?.name ?? customer;
}

function NewCard({ order: o, first, defaultPrep, act }: { order: Order; first: boolean; defaultPrep: number; act: (fn: () => Promise<unknown>) => Promise<void> }) {
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
          <Text style={[textFont("800"), { fontSize: 18 }]}>{code(o.id)} · {name(o, tr("partner.orders.customer"))}</Text>
          <Text style={[t.muted, { marginTop: 2 }]}>{tr("partner.orders.delivery_paid", { time: clock(o.placed_at ?? o.created_at) })}</Text>
        </View>
        {left != null ? (
          <View style={{ alignItems: "flex-end" }} accessibilityLabel={tr("partner.orders.left_to_accept", { min: Math.floor(left / 60), sec: left % 60 })}>
            <Text style={[textFont("800"), { fontSize: 20, color: color.chili, fontVariant: ["tabular-nums"] }]}>
              {Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")}
            </Text>
            <Text style={{ ...textFont("400"), fontSize: 11, color: color.muted }}>{tr("partner.orders.to_accept")}</Text>
          </View>
        ) : null}
      </View>
      <View style={{ gap: 8 }}>
        {items.map((it, i) => (
          <View key={i}>
            <Text style={t.body}><Text style={textFont("800")}>{it.quantity ?? 1}×</Text> {it.name}</Text>
            {it.options?.length ? <Text style={[t.muted, { marginTop: 2 }]}>{it.options.join(" · ")}</Text> : null}
          </View>
        ))}
        {o.special_instructions ? (
          <View style={s.note}><Text style={[textFont("600"), { fontSize: 13, color: tone.kesarInk }]}>{tr("partner.orders.note", { note: o.special_instructions })}</Text></View>
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

function CookingCard({ order: o, act }: { order: Order; act: (fn: () => Promise<unknown>) => Promise<void> }) {
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
        <Text style={[textFont("700"), { fontSize: 13, color: left < 0 ? color.chili : tone.kesarInk }]}>
          {almost ? tr("partner.orders.almost_ready_label") : left < 0 ? tr("partner.orders.late", { min: -left }) : tr("partner.orders.left", { min: left })}
        </Text>
      </View>
      <Text style={[t.muted, { fontSize: 14 }]}>{items.map((i) => `${i.quantity ?? 1}× ${i.name}`).join(" · ")}</Text>
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
        <Text style={[textFont("700"), { fontSize: 13, color: color.peacockDeep }]}>{tr("partner.orders.ready_at", { time: clock(o.actual_ready_at) })}</Text>
      </View>
      <Text style={[t.muted, { fontSize: 14 }]}>{[...items.map((i) => `${i.quantity ?? 1}× ${i.name}`), tr("partner.orders.bags", { count: bags })].join(" · ")}</Text>
      <View style={s.rider}>
        <View style={s.avatar}><Text style={[textFont("800"), { color: color.peacockDeep }]}>{rname ? rname.split(/\s+/).filter(Boolean).map((p) => [...p][0]).join("").slice(0, 2).toUpperCase() : "…"}</Text></View>
        <View style={{ flex: 1 }}>
          <Text style={[textFont("700"), { fontSize: 14 }]}>
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
