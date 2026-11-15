// The customer's own orders for the home screen: the one on its way (the
// active-order bar) and "Order again" (the latest delivered order per kitchen).
import { api, unwrap, useBag, type CoreSchemas } from "@bhojango/mobile-core";
import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";

import type { Order } from "./contract";

/** Recent orders, refreshed whenever the screen comes back into view (null until loaded). */
export function useMyOrders(limit = 20) {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const load = useCallback(() => {
    let live = true;
    api.core
      .GET("/api/v1/orders", { params: { query: { limit } } })
      .then((r) => live && setOrders((unwrap(r) as { items: Order[] }).items))
      .catch(() => live && setOrders((o) => o ?? []));
    return () => {
      live = false;
    };
  }, [limit]);
  useFocusEffect(load);
  return orders;
}

/**
 * Puts an old order's dishes (those still available) in a new bag
 * (POST /orders/{id}/reorder works out what's available now; nothing is placed).
 * Returns false when none of them is available.
 */
export async function reorder(order: Order): Promise<boolean> {
  const r = unwrap(await api.core.POST("/api/v1/orders/{order_id}/reorder", { params: { path: { order_id: order.id } } })) as CoreSchemas["ReorderResponse"];
  const bag = useBag.getState();
  const items = r.items.filter((x) => x.available !== false);
  if (!items.length) return false;
  bag.clear();
  for (const it of items) {
    const picks = (it.options ?? []).map((p) => ({ group: p.group, option: p.option }));
    bag.add({ id: r.restaurant.id, name: r.restaurant.name }, {
      menuItemId: it.menu_item_id, name: it.name, unitPrice: Number(it.price), quantity: it.quantity, picks,
      summary: picks.map((p) => p.option.split(" · ")[0]?.toLowerCase()).join(", "),
    });
  }
  return true;
}
