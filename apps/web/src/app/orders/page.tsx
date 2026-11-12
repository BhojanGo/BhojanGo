"use client";
// Your orders: what's on its way first, then past orders.
import { ACTIVE_STATUSES, unwrap, type CoreSchemas, type OrderStatus } from "@bhojango/api-client";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api, useHydrated, useSession } from "@/lib/client";
import { StatusPill } from "@bhojango/ui";
import { money } from "@bhojango/ui/bill";

type Order = CoreSchemas["OrderResponse"];

export default function Orders() {
  const ready = useHydrated();
  const user = useSession((s) => s.user);
  const signOut = useSession((s) => s.signOut);
  const [orders, setOrders] = useState<Order[] | null>(null);
  useEffect(() => {
    if (!ready || !user) return;
    api.core.GET("/api/v1/orders", { params: { query: { limit: 50 } } }).then((r) => setOrders(unwrap(r).items)).catch(() => setOrders([]));
  }, [ready, user]);

  if (ready && !user) {
    return (
      <div className="mx-auto max-w-md px-5 py-20 text-center">
        <h1 className="font-display text-3xl font-semibold">Sign in to see your orders</h1>
        <Link href="/sign-in?next=/orders" className="mt-6 inline-flex h-12 items-center rounded-pill bg-peacock px-6 font-extrabold text-white">Sign in</Link>
      </div>
    );
  }
  const visible = (orders ?? []).filter((o) => o.status !== "pending_payment");
  const active = visible.filter((o) => ACTIVE_STATUSES.includes(o.status as OrderStatus));
  const past = visible.filter((o) => !ACTIVE_STATUSES.includes(o.status as OrderStatus));
  const row = (o: Order) => (
    <li key={o.id}>
      <Link href={`/orders/${o.id}`} className="flex items-center gap-4 rounded-card bg-white p-5 hover:shadow-float">
        <div className="min-w-0 flex-1">
          <p className="font-extrabold">{o.restaurant_name}</p>
          <p className="truncate text-sm text-muted">
            {new Date(o.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })} · {(o.items as { name?: string; quantity?: number }[]).map((i) => `${i.quantity ?? 1}× ${i.name}`).join(", ")}
          </p>
        </div>
        <StatusPill status={o.status} />
        <span className="w-24 text-right font-bold tabular-nums">{money(Number(o.total), o.currency)}</span>
      </Link>
    </li>
  );
  return (
    <div className="mx-auto max-w-3xl space-y-8 px-5 py-10">
      <div className="flex items-baseline justify-between">
        <h1 className="font-display text-4xl font-semibold tracking-[-1px]">Your orders</h1>
        {user ? <button type="button" className="text-sm font-bold text-muted hover:text-chili" onClick={() => void signOut()}>Sign out</button> : null}
      </div>
      {orders === null ? <p className="text-muted">Loading…</p> : null}
      {active.length ? <section><h2 className="mb-3 text-lg font-extrabold">On its way</h2><ul className="space-y-3">{active.map(row)}</ul></section> : null}
      {past.length ? <section><h2 className="mb-3 text-lg font-extrabold">Past orders</h2><ul className="space-y-3">{past.map(row)}</ul></section> : null}
      {orders && !visible.length ? <p className="text-muted">No orders yet. <Link href="/" className="font-bold text-peacock">Find something to eat</Link></p> : null}
    </div>
  );
}
