"use client";
/**
 * R29: a kitchen's payout statement, order by order: food subtotal − commission − card fee (− offers it funded,
 * − refunds that were its fault, − tax on commission / TDS where they apply) = payout. GET /finance/statements/{id}.
 */
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { use } from "react";

import { ConsoleShell } from "@/components/console/ConsoleShell";
import { adminApi } from "@/lib/api";
import { apiMessage, money } from "@/lib/ops";

interface Line {
  order_id: string; delivered_at: string; food: string; packaging: string; commission: string; card_fee?: string;
  restaurant_funded_offers: string; refunds: string; commission_tax: string; tds: string; net: string;
  // a delivery partner's line (R30/R31): the order's delivery fee + the whole tip, and the road distance
  distance_units?: string; delivery_fee?: string; tip?: string; total?: string; base?: string; distance?: string; waiting?: string;
}
interface Statement {
  id: string; payee_type: string; payee_name?: string; amount: number; currency: string; status: string;
  summary: Record<string, string | number | null>; lines: Line[];
}

const code = (id: string) => `#${id.replace(/-/g, "").slice(0, 6).toUpperCase()}`;
const n = (v: string | undefined) => Number(v ?? 0);

export default function StatementPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const st = useQuery({
    queryKey: ["statement", id],
    queryFn: async () => (await adminApi.get<Statement>(`/user/finance/statements/${id}`)).data,
  });
  const s = st.data;
  const cur = s?.currency ?? "USD";
  const extra = s ? (["restaurant_funded_offers", "refunds", "commission_tax", "tds"] as const).filter((k) => s.lines.some((l) => n(l[k]) !== 0)) : [];
  const label: Record<string, string> = { restaurant_funded_offers: "Offers it funded", refunds: "Its refunds", commission_tax: "Tax on commission", tds: "TDS" };
  if (s?.payee_type === "rider") return <PartnerStatement s={s} />;
  return (
    <ConsoleShell section="Finance" country={cur === "INR" ? "IN" : "US"} hideScope>
      <div>
        <div className="text-small text-muted"><Link href="/finance" className="text-peacock">Finance</Link> ▸ Restaurant statement</div>
        <h1 className="m-0 mt-2 text-h1">{s?.payee_name ?? "Restaurant statement"}</h1>
        <p className="mt-1 text-small text-muted">Each order: food subtotal − commission − card processing fee (on the whole charge, tip included) = what the restaurant is paid.</p>
      </div>
      {st.isError ? <p role="alert">{apiMessage(st.error)}</p> : null}
      {s ? (
        <div className="table-scroll">{/* R41: scrolls inside its card on a phone, never the page */}<table className="w-full rounded-2xl bg-white text-left" data-testid="statement-lines">
          <thead>
            <tr className="text-small text-muted">
              <th className="p-3">Order</th><th className="p-3">Delivered</th><th className="p-3 text-right">Food subtotal</th>
              <th className="p-3 text-right">Commission</th><th className="p-3 text-right">Card fee</th>
              {extra.map((k) => <th key={k} className="p-3 text-right">{label[k]}</th>)}
              <th className="p-3 text-right">Payout</th>
            </tr>
          </thead>
          <tbody>
            {s.lines.map((l) => (
              <tr key={l.order_id} className="border-t border-line-soft tabular-nums" data-testid="statement-line">
                <td className="p-3 font-semibold">{code(l.order_id)}</td>
                <td className="p-3 text-small">{new Date(l.delivered_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</td>
                <td className="p-3 text-right">{money(n(l.food) + n(l.packaging), cur, 2)}</td>
                <td className="p-3 text-right">{money(n(l.commission), cur, 2)}</td>
                <td className="p-3 text-right">{money(n(l.card_fee), cur, 2)}</td>
                {extra.map((k) => <td key={k} className="p-3 text-right">{money(n(l[k]), cur, 2)}</td>)}
                <td className="p-3 text-right font-bold">{money(n(l.net), cur, 2)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-line tabular-nums">
              <td className="p-3 font-bold" colSpan={2}>{s.lines.length} {s.lines.length === 1 ? "order" : "orders"}</td>
              <td className="p-3 text-right">{money(n(String(s.summary.food)) + n(String(s.summary.packaging ?? 0)), cur, 2)}</td>
              <td className="p-3 text-right">{money(-n(String(s.summary.commission)) || 0, cur, 2)}</td>
              <td className="p-3 text-right">{money(-n(String(s.summary.card_fee ?? 0)) || 0, cur, 2)}</td>
              {extra.map((k) => <td key={k} className="p-3 text-right">{money(-n(String(s.summary[k] ?? 0)) || 0, cur, 2)}</td>)}
              <td className="p-3 text-right font-bold">{money(n(String(s.summary.net)), cur, 2)}</td>
            </tr>
          </tfoot>
        </table></div>
      ) : null}
    </ConsoleShell>
  );
}

/** R31: a delivery partner's statement: each trip's road distance (2 decimals), delivery fee and tip. */
function PartnerStatement({ s }: { s: Statement }) {
  const cur = s.currency;
  const unit = cur === "USD" ? "mi" : "km";
  const pay = (l: Line) => (l.delivery_fee != null ? n(l.delivery_fee) : n(l.base) + n(l.distance) + n(l.waiting));
  return (
    <ConsoleShell section="Finance" country={cur === "INR" ? "IN" : "US"} hideScope>
      <div>
        <div className="text-small text-muted"><Link href="/finance" className="text-peacock">Finance</Link> ▸ Delivery partner statement</div>
        <h1 className="m-0 mt-2 text-h1">{s.payee_name ?? "Delivery partner statement"}</h1>
        <p className="mt-1 text-small text-muted">Each trip: the order&apos;s delivery fee (from the road distance) + 100% of the tip. BhojanGo never adds to or takes from it.</p>
      </div>
      <div className="table-scroll">{/* R41: scrolls inside its card on a phone, never the page */}<table className="w-full rounded-2xl bg-white text-left" data-testid="statement-lines">
        <thead>
          <tr className="text-small text-muted">
            <th className="p-3">Order</th><th className="p-3">Delivered</th><th className="p-3 text-right">Road distance</th>
            <th className="p-3 text-right">Delivery fee</th><th className="p-3 text-right">Tip</th><th className="p-3 text-right">Paid</th>
          </tr>
        </thead>
        <tbody>
          {s.lines.map((l) => (
            <tr key={l.order_id} className="border-t border-line-soft tabular-nums" data-testid="statement-line">
              <td className="p-3 font-semibold">{code(l.order_id)}</td>
              <td className="p-3 text-small">{new Date(l.delivered_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</td>
              <td className="p-3 text-right" data-testid="distance">{n(l.distance_units).toFixed(2)} {unit}</td>
              <td className="p-3 text-right">{money(pay(l), cur, 2)}</td>
              <td className="p-3 text-right">{money(n(l.tip), cur, 2)}</td>
              <td className="p-3 text-right font-bold">{money(n(l.total), cur, 2)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-line tabular-nums">
            <td className="p-3 font-bold" colSpan={3}>{s.lines.length} {s.lines.length === 1 ? "trip" : "trips"}</td>
            <td className="p-3 text-right">{money(s.lines.reduce((a, l) => a + pay(l), 0), cur, 2)}</td>
            <td className="p-3 text-right">{money(s.lines.reduce((a, l) => a + n(l.tip), 0), cur, 2)}</td>
            <td className="p-3 text-right font-bold">{money(s.lines.reduce((a, l) => a + n(l.total), 0), cur, 2)}</td>
          </tr>
        </tfoot>
      </table></div>
    </ConsoleShell>
  );
}
