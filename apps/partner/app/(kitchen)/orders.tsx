// PartnerOrders.html: New (ring, accept timer, "ready in" picker), Preparing
// (time left, almost ready, mark ready), Ready for pickup (rider on the way).
import { api, ApiError, unwrap } from "@bhojango/mobile-core";
import { useEffect, useState } from "react";
import { Alert, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { COOKING, NEW, READY, useBoard } from "../../lib/board";
import { cash, clock, code, move, reject, riderEta, useKitchen, type Order, type Today } from "../../lib/data";
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
  const fresh = orders.filter((o) => NEW.includes(o.status)).sort((a, b) => a.created_at.localeCompare(b.created_at));
  const cooking = orders.filter((o) => COOKING.includes(o.status));
  const ready = orders.filter((o) => READY.includes(o.status));

  async function act(fn: () => Promise<unknown>) {
    try {
      await fn();
    } catch (e) {
      Alert.alert("That didn't go through", e instanceof ApiError ? e.message : (e as Error).message);
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
    <SafeAreaView edges={["top", "right"]} style={{ flex: 1 }}>
      <Header today={today} onBusy={busy} onPause={() => (today?.paused ? pause(null, false) : setPausing(true))} />
      {error ? <Text style={[t.muted, { color: color.chili, paddingHorizontal: 24, paddingTop: 8 }]}>{error}</Text> : null}
      <View style={s.board}>
        <Column title="New" count={fresh.length} badge={[color.peacock, color.white]}>
          {fresh.length === 0 ? <Text style={t.muted}>New orders ring here.</Text> : null}
          {fresh.map((o, i) => <NewCard key={o.id} order={o} first={i === 0} defaultPrep={today?.prep_minutes ?? 20} act={act} />)}
        </Column>
        <Column title="Preparing" count={cooking.length} badge={[tone.kesarSoft, tone.kesarInk]}>
          {cooking.map((o) => <CookingCard key={o.id} order={o} act={act} />)}
        </Column>
        <Column title="Ready for pickup" count={ready.length} badge={[color.peacockTint, color.peacockDeep]}>
          {ready.map((o) => <ReadyCard key={o.id} order={o} />)}
          <Text style={[t.muted, { textAlign: "center", marginTop: 4 }]}>Orders leave this column when the rider confirms pickup.</Text>
        </Column>
      </View>
      <Modal visible={pausing} transparent animationType="fade" onRequestClose={() => setPausing(false)}>
        <Pressable style={s.scrim} onPress={() => setPausing(false)}>
          <View style={s.sheet} accessibilityLabel="Pause orders">
            <Text style={t.h1}>Pause new orders</Text>
            <Text style={t.muted}>Customers see you&apos;re paused. Orders already placed carry on.</Text>
            <View style={{ flexDirection: "row", gap: 12 }}>
              {[15, 30, 60].map((m) => <Btn key={m} title={`${m} min`} grow onPress={() => pause(m)} />)}
              <Btn title="Until I resume" grow kind="dark" onPress={() => pause(null)} />
            </View>
          </View>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

function Header({ today, onBusy, onPause }: { today: Today | null; onBusy: () => void; onPause: () => void }) {
  const kitchen = useKitchen((s) => s.kitchen)!;
  const cur = today?.currency ?? kitchen.currency;
  const open = today && today.open_now && !today.paused;
  const closes = today?.closes_at ? clock(`2000-01-01T${today.closes_at}:00`) : null;
  const status = !today ? "…" : today.paused
    ? today.paused_until ? `Paused till ${clock(today.paused_until)}` : "Paused"
    : open ? (closes ? `Open till ${closes}` : "Open") : today.reason ?? "Closed";
  return (
    <View style={s.header}>
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text accessibilityRole="header" style={t.h1} numberOfLines={1}>{today?.name ?? kitchen.name}</Text>
        <Text style={[t.muted, { marginTop: 2 }]}>
          {[today?.area, today ? `today ${today.today_orders} orders` : null, today ? cash(today.today_sales, cur) : null].filter(Boolean).join(" · ")}
        </Text>
      </View>
      <View style={[s.status, !open && { backgroundColor: tone.kesarSoft }]} accessibilityLabel={status}>
        <View style={[s.dot, { backgroundColor: open ? color.peacock : tone.kesarInk }]} />
        <Text style={[textFont("800"), { fontSize: 14, color: open ? color.peacockDeep : tone.kesarInk }]}>{status}</Text>
      </View>
      <Btn title={today && today.busy_extra_minutes > 0 ? `Busy · +${today.busy_extra_minutes} min · undo` : "Busy? Add 10 min"} onPress={onBusy} />
      <Btn title={today?.paused ? "Resume orders" : "Pause orders"} kind={today?.paused ? "dark" : "outline"} onPress={onPause} />
    </View>
  );
}

function Column({ title, count, badge, children }: { title: string; count: number; badge: [string, string]; children: React.ReactNode }) {
  return (
    <View style={s.col} accessibilityLabel={title}>
      <View style={s.colHead}>
        <Text style={[textFont("800"), { fontSize: 15 }]}>{title}</Text>
        <Count n={count} bg={badge[0]} fg={badge[1]} />
      </View>
      <ScrollView contentContainerStyle={{ gap: 12, paddingBottom: 24 }} showsVerticalScrollIndicator={false}>{children}</ScrollView>
    </View>
  );
}

function name(o: Order) {
  return (o.customer as { name?: string } | null)?.name ?? "Customer";
}

function NewCard({ order: o, first, defaultPrep, act }: { order: Order; first: boolean; defaultPrep: number; act: (fn: () => Promise<unknown>) => Promise<void> }) {
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
          <Text style={[textFont("800"), { fontSize: 18 }]}>{code(o.id)} · {name(o)}</Text>
          <Text style={[t.muted, { marginTop: 2 }]}>Delivery · paid · {clock(o.placed_at ?? o.created_at)}</Text>
        </View>
        {left != null ? (
          <View style={{ alignItems: "flex-end" }} accessibilityLabel={`${Math.floor(left / 60)} minutes ${left % 60} seconds to accept`}>
            <Text style={[textFont("800"), { fontSize: 20, color: color.chili, fontVariant: ["tabular-nums"] }]}>
              {Math.floor(left / 60)}:{String(left % 60).padStart(2, "0")}
            </Text>
            <Text style={{ ...textFont("400"), fontSize: 11, color: color.muted }}>to accept</Text>
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
          <View style={s.note}><Text style={[textFont("600"), { fontSize: 13, color: tone.kesarInk }]}>Note: {o.special_instructions}</Text></View>
        ) : null}
      </View>
      <View>
        <Text style={[t.label, { marginBottom: 8 }]}>Ready in</Text>
        <Segmented label="Ready in" value={prep} onChange={setPrep}
          options={PREP.map((m) => ({ value: m, label: m === prep ? `${m} min` : String(m) }))} />
      </View>
      <View style={{ flexDirection: "row", gap: 12 }}>
        <Btn title="Reject" kind="danger" height={56} busy={busy === "reject"}
          onPress={() => Alert.alert("Reject this order?", "The customer gets a full refund. Rejections count against your kitchen's rating.", [
            { text: "Keep it", style: "cancel" }, { text: "Reject", style: "destructive", onPress: run("reject", () => reject(o.id)) }])} />
        <Btn testID={first ? "accept" : undefined} title={`Accept · ${cash(o.subtotal, o.currency)}`} kind="primary" height={56} grow
          busy={busy === "accept"} onPress={run("accept", async () => { await move(o.id, "accepted", prep); await move(o.id, "preparing"); })} />
      </View>
    </Card>
  );
}

function CookingCard({ order: o, act }: { order: Order; act: (fn: () => Promise<unknown>) => Promise<void> }) {
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
        <Text style={t.title}>{code(o.id)} · {name(o)}</Text>
        <Text style={[textFont("700"), { fontSize: 13, color: left < 0 ? color.chili : tone.kesarInk }]}>
          {almost ? "almost ready" : left < 0 ? `${-left} min late` : `${left} min left`}
        </Text>
      </View>
      <Text style={[t.muted, { fontSize: 14 }]}>{items.map((i) => `${i.quantity ?? 1}× ${i.name}`).join(" · ")}</Text>
      <View style={s.track}><View style={[s.fill, { width: `${Math.round(done * 100)}%` }]} /></View>
      <View style={{ flexDirection: "row", gap: 8, marginTop: 4 }}>
        {!almost ? (
          <Btn title="Almost ready" onPress={() => act(async () => {
            if (o.status === "accepted") await move(o.id, "preparing");
            await move(o.id, "almost_ready");
          })} />
        ) : null}
        <Btn title="Mark ready" kind="dark" grow onPress={() => act(async () => {
          if (o.status === "accepted") await move(o.id, "preparing");
          await move(o.id, "ready");
        })} />
      </View>
    </Card>
  );
}

function ReadyCard({ order: o }: { order: Order }) {
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
        <Text style={t.title}>{code(o.id)} · {name(o)}</Text>
        <Text style={[textFont("700"), { fontSize: 13, color: color.peacockDeep }]}>ready {clock(o.actual_ready_at)}</Text>
      </View>
      <Text style={[t.muted, { fontSize: 14 }]}>{items.map((i) => `${i.quantity ?? 1}× ${i.name}`).join(" · ")} · {bags} {bags === 1 ? "bag" : "bags"}</Text>
      <View style={s.rider}>
        <View style={s.avatar}><Text style={[textFont("800"), { color: color.peacockDeep }]}>{rname ? rname.replace(/[^A-Za-z ]/g, "").split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase() : "…"}</Text></View>
        <View>
          <Text style={[textFont("700"), { fontSize: 14 }]}>
            {rname ? `${rname} · ${eta == null ? "on the way" : eta <= 1 ? "arriving" : `${eta} min away`}` : "Finding a rider"}
          </Text>
          <Text style={t.muted}>Order code {code(o.id)}</Text>
        </View>
      </View>
    </Card>
  );
}

const s = StyleSheet.create({
  header: {
    height: 80, paddingHorizontal: 24, backgroundColor: color.white, borderBottomWidth: 1, borderBottomColor: color.line,
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
  sheet: { width: 640, backgroundColor: color.white, borderRadius: radius.sheet, padding: 32, gap: 16 },
});
