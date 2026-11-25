"use client";
// R43: a restaurant's menu history (Partners → Restaurants → the restaurant): every change the restaurant or an admin
// made to its menu (dishes, prices, categories, option groups), who made it, when, and each field's old → new value.
// From GET /restaurants/{id}/menu/history (partners.view for the restaurant's city), newest first, 30 at a time.
import { useInfiniteQuery } from "@tanstack/react-query";

import { adminApi } from "@/lib/api";
import { apiMessage, money } from "@/lib/ops";

type Change = { id: string; at: string; who: string; actor_kind: string; entity: string; name: string; action: string;
  changes: { field: string; old: unknown; new: unknown }[] };
type Page = { changes: Change[]; next: string | null };

const FIELD: Record<string, string> = {
  name: "Name", description: "Description", price: "Price", image_url: "Photo", category: "Category", is_veg: "Veg",
  spice_level: "Spice", is_available: "On the menu", available_from: "Served from", available_until: "Served until",
  sold_out_today: "Sold out today", options: "Option groups", min_picks: "At least", max_picks: "At most", is_active: "Shown", order: "Order",
};
const SPICE = ["None", "Mild", "Medium", "Hot"];

function shown(field: string, v: unknown, currency: string): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (field === "price") return money(String(v), currency);
  if (field === "spice_level") return SPICE[Number(v)] ?? String(v);
  if (field === "image_url") return "photo";
  return String(v);
}

export function MenuHistory({ restaurantId, currency, timeZone }: { restaurantId: string; currency: string; timeZone?: string }) {
  const q = useInfiniteQuery({
    queryKey: ["menu-history", restaurantId],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }) => (await adminApi.get<Page>(`/user/restaurants/${restaurantId}/menu/history`,
      { params: { limit: 30, ...(pageParam ? { before: pageParam } : {}) } })).data,
    getNextPageParam: (last) => last.next,
  });
  const rows = q.data?.pages.flatMap((p) => p.changes) ?? [];
  // the restaurant's city clock (never the admin's own)
  const when = (iso: string) => new Date(iso).toLocaleString("en-US", { timeZone, dateStyle: "medium", timeStyle: "short" });
  return (
    <section aria-labelledby="menu-history-h" data-testid="menu-history" className="mt-6 rounded-2xl border border-line bg-white p-5">
      <h3 id="menu-history-h" className="m-0 text-h3">Menu history</h3>
      <p className="text-small text-muted">Changes to this restaurant&apos;s menu by the restaurant and by admins, newest first.</p>
      {q.isError ? <p role="alert" className="text-small text-chili">{apiMessage(q.error)}</p> : null}
      {q.isLoading ? <p className="text-small text-muted">Loading…</p> : null}
      {q.isSuccess && rows.length === 0 ? <p data-testid="menu-history-empty" className="text-small text-muted">No menu changes yet.</p> : null}
      {rows.length ? (
        <div className="table-scroll mt-3">
          <table className="table-stack w-full text-left text-small">
            <thead className="text-caption text-muted"><tr><th className="py-2 pr-3">When{timeZone ? ` (${timeZone})` : ""}</th><th>Who</th><th>What</th><th>Change</th></tr></thead>
            <tbody className="divide-y divide-line">
              {rows.map((c) => (
                <tr key={c.id} data-testid="menu-history-row">
                  <td data-label="When" className="py-2 pr-3 tabular-nums whitespace-nowrap">{when(c.at)}</td>
                  <td data-label="Who">{c.who}<span className="text-muted"> · {c.actor_kind}</span></td>
                  <td data-label="What"><b>{c.name}</b> <span className="text-muted">({c.entity}) {c.action}</span></td>
                  <td data-label="Change" className="tabular-nums">
                    {c.action === "added" ? "—" : c.changes.map((x) => (
                      <div key={x.field}>{FIELD[x.field] ?? x.field}: {shown(x.field, x.old, currency)} → {shown(x.field, x.new, currency)}</div>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {q.hasNextPage ? (
        <button type="button" onClick={() => void q.fetchNextPage()} disabled={q.isFetchingNextPage} className="mt-3 min-h-11 rounded-full border border-line px-4 font-bold">
          Show older
        </button>
      ) : null}
    </section>
  );
}
