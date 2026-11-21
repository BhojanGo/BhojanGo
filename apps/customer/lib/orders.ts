// The customer's own orders for the home screen: the one on its way (the
// active-order bar) and "Order again" (the latest delivered order per kitchen).
import { api, reorderToBag, unwrap, useBag, type CoreSchemas } from "@bhojango/mobile-core";
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
 * Puts an old order's dishes (those still available, with the same options and quantities) in a new bag
 * (POST /orders/{id}/reorder works out what's available now; nothing is placed). R27: `added` is false when
 * none of them is available; `notes` are message keys saying what changed (sold out, an option no longer offered).
 */
export async function reorder(order: Order): Promise<{ added: boolean; notes: { key: string; values: Record<string, string> }[] }> {
  const r = unwrap(await api.core.POST("/api/v1/orders/{order_id}/reorder", { params: { path: { order_id: order.id } } })) as CoreSchemas["ReorderResponse"];
  const { restaurant, lines, notes } = reorderToBag(r, "account.receipt.reorder");
  if (!lines.length) return { added: false, notes };
  const bag = useBag.getState();
  bag.clear();
  for (const line of lines) bag.add({ id: restaurant.id, name: restaurant.name }, line);
  return { added: true, notes };
}
