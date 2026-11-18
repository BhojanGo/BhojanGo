// One order's receipt (the website's Receipt): the kitchen and when, the items
// with their options, the full fair bill with who gets what (tax included),
// the total, how it was paid and where it went; the PDF (a tax invoice where
// the bill carries GST) through the share sheet, order again, track, rate a
// delivered order, report a problem. Money in the order's currency.
import { Button, color, FairBill, inZone, num, SafeAreaView, space, type, useBag, useCountry, useI18n } from "@bhojango/mobile-core";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { ScrollView, Text, View } from "react-native";

import {
  billLines, getBill, getOrder, isActive, itemOptions, orderCode, payLabel, reorder, shareReceipt, statusLabel,
  type Bill, type Order, type OrderItem,
} from "../../../lib/account";
import { RateOrder } from "../../../lib/account-rating";
import { ScreenBar, Section, Status, ui } from "../../../lib/account-ui";

export default function Receipt() {
  const { t, money, date, time } = useI18n();
  const { countries } = useCountry();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [data, setData] = useState<{ order: Order; bill: Bill | null } | null | "error">(null);
  const [busy, setBusy] = useState<"pdf" | "again" | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [missing, setMissing] = useState<{ names: string[]; added: boolean } | null>(null);

  const load = useCallback(() => {
    Promise.all([getOrder(id), getBill(id)])
      .then(([order, bill]) => setData({ order, bill }))
      .catch(() => setData("error"));
  }, [id]);
  useEffect(load, [load]);

  const code = orderCode(id);
  if (data === null || data === "error") {
    return (
      <SafeAreaView style={ui.screen} edges={["top", "left", "right"]}>
        <ScreenBar title={code} fallback="/orders" />
        <View style={{ padding: space[5] }}>
          <Status loading={data === null} error={data === "error" ? t("account.receipt.not_found") : null} onRetry={() => { setData(null); load(); }} />
        </View>
      </SafeAreaView>
    );
  }

  const { order, bill } = data;
  const at = order.placed_at ?? order.created_at;
  const tz = inZone(order.time_zone); // every time here is the order's city's, never the phone's
  const delivered = order.status === "delivered" && order.actual_delivery_time ? order.actual_delivery_time : null;
  const minutes = delivered ? Math.max(1, Math.round((new Date(delivered).getTime() - new Date(at).getTime()) / 60000)) : 0;
  const active = isActive(order.status);
  const cancelled = order.status === "cancelled";
  const gst = (bill?.lines ?? []).some((l) => /\bGST\b/i.test(l.label)); // the bill says which: a GST bill gets a tax invoice
  const items = (order.items ?? []) as OrderItem[];
  const addr = (order.delivery_address ?? {}) as { label?: string; street?: string; city?: string };
  const pdfTitle = gst ? t("account.receipt.tax_invoice") : t("account.receipt.receipt_pdf");

  async function pdf() {
    setBusy("pdf");
    setProblem(null);
    try {
      await shareReceipt(order.id, pdfTitle);
    } catch {
      setProblem(t("account.receipt.download_failed"));
    } finally {
      setBusy(null);
    }
  }

  async function again() {
    setBusy("again");
    setProblem(null);
    setMissing(null);
    try {
      const r = await reorder(order.id);
      const ok = r.items.filter((i) => i.available !== false);
      const names = [...r.unavailable, ...r.items.filter((i) => i.available === false).map((i) => i.name)];
      if (ok.length) {
        const bag = useBag.getState();
        bag.clear();
        for (const i of ok) {
          bag.add({ id: r.restaurant.id, name: r.restaurant.name }, {
            menuItemId: i.menu_item_id, name: i.name, unitPrice: Number(i.price), quantity: i.quantity,
            picks: i.options.map((o) => ({ group: o.group, option: o.option })),
            summary: i.options.map((o) => o.name ?? o.option).join(", "),
          });
        }
      }
      if (!names.length) router.push("/bag");
      else setMissing({ names, added: ok.length > 0 });
    } catch {
      setProblem(t("account.receipt.reorder_failed"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <SafeAreaView style={ui.screen} edges={["top", "left", "right"]}>
      <ScreenBar title={code} fallback="/orders" testID="receipt-title" />
      <ScrollView testID="receipt" contentContainerStyle={ui.scroll}>
        <View accessible accessibilityLabel={t("account.receipt.label", { code })} style={{ gap: 4 }}>
          <Text accessibilityRole="header" style={[type.h2, { color: color.kohl }]}>{order.restaurant_name}</Text>
          <Text testID="receipt-status" style={ui.muted}>
            {delivered
              ? t("account.receipt.delivered_line", { date: date(delivered, tz), time: time(delivered, tz), minutes, code })
              : t("account.receipt.status_line", { status: statusLabel(t, order.status), date: date(at, tz), time: time(at, tz), code })}
          </Text>
        </View>

        <View style={{ gap: space[2] }}>
          {active ? <Button testID="track-order" title={t("account.receipt.track")} block onPress={() => router.push(`/order/${order.id}`)} /> : null}
          {!active ? (
            <Button testID="order-again" title={busy === "again" ? t("account.receipt.adding") : t("account.receipt.order_again")} block
              loading={busy === "again"} disabled={busy !== null} onPress={again} />
          ) : null}
          {!cancelled ? (
            <Button testID="receipt-pdf" title={busy === "pdf" ? t("account.receipt.downloading") : pdfTitle} variant="secondary" block
              loading={busy === "pdf"} disabled={busy !== null} onPress={pdf} />
          ) : null}
          {!cancelled ? (
            <Button testID="receipt-report" title={t("account.receipt.report")} variant="secondary" block onPress={() => router.push(`/report/${order.id}`)} />
          ) : null}
          {problem ? <Text accessibilityRole="alert" style={ui.error}>{problem}</Text> : null}
          {missing ? (
            <View accessibilityRole="alert" style={{ backgroundColor: color.plate, borderRadius: 16, padding: space[4], gap: 6 }}>
              <Text style={[type.label, { color: color.kohl }]}>
                {missing.added ? t("account.receipt.unavailable", { items: missing.names.join(", ") }) : t("account.receipt.none_available")}
              </Text>
              {missing.added ? <Button title={t("account.receipt.continue_checkout")} variant="ghost" onPress={() => router.push("/bag")} /> : null}
            </View>
          ) : null}
        </View>

        {order.status === "delivered" ? <RateOrder key={order.id} order={order} /> : null}

        <Section title={t("account.receipt.items")} testID="receipt-items">
          {items.map((i, n) => {
            const opts = itemOptions(i);
            const line = i.total ?? (i.unit_price != null ? i.unit_price * (i.quantity ?? 1) : null);
            return (
              <View key={`${i.menu_item_id}-${n}`} style={{ flexDirection: "row", justifyContent: "space-between", gap: space[3] }}>
                <Text style={[type.body, { flex: 1, color: color.kohl }]}>
                  {i.quantity ?? 1} × {i.name}
                  {opts ? <Text style={{ color: color.muted }}> · {opts}</Text> : null}
                </Text>
                {line != null ? <Text style={[type.label, num, { color: color.kohl }]}>{money(line, order.currency)}</Text> : null}
              </View>
            );
          })}
        </Section>

        <View testID="receipt-bill" style={{ gap: space[2] }}>
          {bill ? (
            <FairBill lines={billLines(t, bill)} currency={bill.currency} totalLabel={cancelled ? t("account.receipt.total") : t("account.receipt.you_paid")} />
          ) : (
            <Section title={t("account.receipt.fair_bill")}>
              <Text style={ui.muted}>{t("account.receipt.no_bill")}</Text>
              <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
                <Text style={[type.h3, { color: color.kohl }]}>{t("account.receipt.total")}</Text>
                <Text style={[type.h3, num, { color: color.kohl }]}>{money(order.total, order.currency)}</Text>
              </View>
            </Section>
          )}
          {!cancelled && order.placed_at ? (
            <Text testID="receipt-time" style={ui.small}>{t("account.receipt.paid_with", { method: payLabel(t, order.payment_method), date: date(order.placed_at, tz), time: time(order.placed_at, tz) })}</Text>
          ) : null}
          {(() => {
            // R15: who operates BhojanGo in the order's country (Markets), never a name in code.
            const operator = countries.find((c) => c.currency === order.currency)?.legal?.name;
            return operator ? <Text testID="receipt-operator" style={ui.small}>{t("common.operated_by", { name: operator })}</Text> : null;
          })()}
        </View>

        {addr.street || addr.label ? (
          <Section title={delivered ? t("account.receipt.delivered_to") : t("account.receipt.deliver_to")}>
            <Text style={ui.muted}>{[addr.label, addr.street, addr.city].filter(Boolean).join(" · ")}</Text>
          </Section>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}
