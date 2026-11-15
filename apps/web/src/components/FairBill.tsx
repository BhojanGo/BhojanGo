// The fair bill (design: WebKitchen "Your bag", WebCheckout, WebOrders receipt):
// every line with who gets it. Lines come from the engine (quote, order bill or
// example bill); amounts are never computed here.
import { money } from "@/lib/format";
import type { BillLine } from "@/lib/server";

type T = (key: string, vars?: Record<string, string | number>) => string;

// Who each line goes to: the delivery and service fees are ours (riders are
// paid separately), tax is the government's, the tip is all the rider's.
const PAYEE: Record<string, "kitchen" | "us" | "tax" | "rider"> = {
  food: "kitchen", packaging: "kitchen", delivery_fee: "us", service_fee: "us", small_order_fee: "us",
  surge: "us", late_night_fee: "us", tax: "tax", tip: "rider",
};
const TRANSLATED = new Set(["food", "packaging", "delivery_fee", "service_fee", "small_order_fee", "surge", "late_night_fee", "tip"]);

export function billLabel(ln: BillLine, t: T, distance?: string | null): string {
  if (!TRANSLATED.has(ln.code)) return ln.label; // tax and offers: the rule's own name (rates, terms)
  const base = t(`bill.line_${ln.code}`);
  return ln.code === "delivery_fee" && distance ? `${base} · ${distance}` : base;
}

export function payeeLabel(ln: BillLine, t: T): string {
  if (ln.code === "promotion") return ln.funded_by === "restaurant" ? t("common.kitchen_pays_caps") : t("common.bhojango_pays");
  const p = PAYEE[ln.code] ?? "us";
  return p === "kitchen" ? t("bill.kitchen") : p === "tax" ? t("bill.tax") : p === "rider" ? t("bill.rider") : t("bill.bhojango");
}

export function FairBill({
  lines,
  total,
  currency,
  formatLocale,
  t,
  distance,
  totalLabel,
  note,
  compact,
}: {
  lines: BillLine[];
  total: string | number;
  currency: string;
  formatLocale: string;
  t: T;
  distance?: string | null;
  totalLabel?: string;
  note?: string;
  compact?: boolean;
}) {
  return (
    <div>
      <table className="w-full border-collapse text-body tabular-nums">
        <tbody>
          {lines.map((ln, i) => {
            const promo = ln.code === "promotion";
            return (
              <tr key={`${ln.code}-${i}`}>
                <td className={`py-[3px] pr-2 ${compact ? "text-small" : ""}`}>{billLabel(ln, t, distance)}</td>
                <td className="py-[3px] pr-3 text-right text-small text-[#4C5A5E]">{payeeLabel(ln, t)}</td>
                <td className={`py-[3px] text-right font-semibold ${promo ? "text-[#0B5D66]" : ""}`}>{money(ln.amount, currency, formatLocale)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="mt-4 flex items-baseline justify-between border-t border-dashed border-[#C9D3D4] pt-4">
        <b className="text-h3">{totalLabel ?? t("bill.total")}</b>
        <b className="text-h3 tabular-nums">{money(total, currency, formatLocale)}</b>
      </div>
      {note && <p className="mt-1 text-small text-[#4C5A5E]">{note}</p>}
    </div>
  );
}

/** "Who gets your money" bar (landing page): shares of an example bill. */
export function MoneyBar({ lines, t }: { lines: BillLine[]; t: T }) {
  const sums = { kitchen: 0, rider: 0, tax: 0, us: 0 };
  for (const ln of lines) {
    const a = Number(ln.amount);
    if (ln.code === "promotion") sums[ln.funded_by === "restaurant" ? "kitchen" : "us"] += a;
    else sums[PAYEE[ln.code] ?? "us"] += a;
  }
  const total = Object.values(sums).reduce((a, b) => a + Math.max(b, 0), 0) || 1;
  const parts = [
    { k: "kitchen", color: "#0B5D66", label: t("bill.kitchen") },
    { k: "rider", color: "#E8A93C", label: t("bill.rider_tip") },
    { k: "tax", color: "#A9B8BA", label: t("bill.tax") },
    { k: "us", color: "#111418", label: t("bill.bhojango") },
  ] as const;
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full" role="img" aria-label={parts.map((p) => `${p.label} ${Math.round((Math.max(sums[p.k], 0) / total) * 100)}%`).join(", ")}>
        {parts.map((p) => (
          <span key={p.k} style={{ width: `${(Math.max(sums[p.k], 0) / total) * 100}%`, background: p.color }} />
        ))}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-small">
        {parts.map((p) => (
          <span key={p.k} className="flex items-center gap-[6px]">
            <span className="h-[10px] w-[10px]" style={{ background: p.color }} />
            {p.label}
          </span>
        ))}
      </div>
    </div>
  );
}
