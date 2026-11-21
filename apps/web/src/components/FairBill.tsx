// The fair bill (design: WebKitchen "Your bag", WebCheckout, WebOrders receipt):
// every line with who gets it. Lines come from the engine (quote, order bill or
// example bill); amounts are never computed here.
import { fairSplit, payeeOf, type Payee, type Shares } from "@/lib/fairSplit";
import { billLineLabel } from "@bhojango/i18n";
import { shownLines } from "@bhojango/ui/bill";
import { money } from "@/lib/format";
import type { BillLine } from "@/lib/server";

type T = (key: string, vars?: Record<string, string | number>) => string;

export function billLabel(ln: BillLine, t: T, distance?: string | null): string {
  // R27: the engine's lines and the known tax lines ("Idaho sales tax", "GST on food") in the
  // language (@bhojango/i18n billLineLabel); offers keep the rule's own name (terms).
  const base = billLineLabel(t, ln);
  return ln.code === "delivery_fee" && distance ? `${base} · ${distance}` : base;
}

export function payeeLabel(ln: BillLine, t: T): string {
  if (ln.code === "promotion") return ln.funded_by === "restaurant" ? t("common.kitchen_pays_caps") : t("common.bhojango_pays");
  const p = payeeOf(ln);
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
          {shownLines(lines).map((ln, i) => { // a line of 0 (a $0.00 tax) is not shown (R12)
            const promo = ln.code === "promotion";
            return (
              <tr key={`${ln.code}-${i}`}>
                <td className={`py-[3px] pr-2 ${compact ? "text-small" : ""}`}>{billLabel(ln, t, distance)}</td>
                <td className="py-[3px] pr-3 text-right text-small text-muted">{payeeLabel(ln, t)}</td>
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
      {note && <p className="mt-1 text-small text-muted">{note}</p>}
    </div>
  );
}

/**
 * "Who gets your money" (landing page): the engine's split of a real bill (the
 * country's example quote): kitchen, delivery partner (pay + tip), tax, BhojanGo, as whole
 * percentages that add up to 100.
 */
export function MoneyBar({ shares, t, formatLocale }: { shares: Shares | null | undefined; t: T; formatLocale: string }) {
  const split = fairSplit(shares);
  if (!split) return null;
  const look: Record<Payee, { color: string; label: string }> = {
    kitchen: { color: "#0B5D66", label: t("bill.kitchen") },
    rider: { color: "#E8A93C", label: t("bill.rider_tip") },
    tax: { color: "#A9B8BA", label: t("bill.tax") },
    us: { color: "#111418", label: t("bill.bhojango") },
  };
  const pct = new Intl.NumberFormat(formatLocale, { style: "percent", maximumFractionDigits: 0 });
  return (
    <div data-testid="money-split">
      <div className="flex h-3 overflow-hidden rounded-full" role="img" aria-label={split.map((p) => `${look[p.payee].label} ${p.percent}%`).join(", ")}>
        {split.map((p) => (
          <span key={p.payee} style={{ width: `${p.percent}%`, background: look[p.payee].color }} />
        ))}
      </div>
      {/* One row per payee (round 20): in two columns a long label ("Delivery partner + tip") wrapped to three
          lines in the home card and pushed its percentage out of line. Each label stays on one line. */}
      <ul className="m-0 mt-3 grid list-none grid-cols-1 gap-y-1 p-0 text-small">
        {split.map((p) => (
          <li key={p.payee} data-payee={p.payee} data-percent={p.percent} className="flex items-center gap-[6px]">
            <span className="h-[10px] w-[10px] shrink-0" style={{ background: look[p.payee].color }} />
            <span data-testid="payee-label" className="min-w-0 flex-grow truncate whitespace-nowrap">{look[p.payee].label}</span>
            <b className="shrink-0 font-semibold tabular-nums text-[#111418]">{pct.format(p.percent / 100)}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}
