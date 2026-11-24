import * as React from "react";
import { billRows, billTotal, money, type BillLine } from "../../bill";
import { cn } from "../lib/utils";

export interface FairBillProps {
  lines: BillLine[];
  currency: string;
  /** "You pay" (checkout) or "You paid" (receipts) */
  totalLabel?: string;
  className?: string;
}

/** The fair bill: every line with who gets the money, then the total. */
export function FairBill({ lines, currency, totalLabel = "You pay", className }: FairBillProps) {
  const rows = billRows(lines, currency);
  return (
    <section aria-label="The fair bill" className={cn("rounded-card bg-white p-4 text-small tabular-nums", className)}>
      <div className="mb-2.5 flex items-baseline justify-between">
        <span className="text-h3">The fair bill</span>
        <span className="text-small text-peacock">who gets each {currency === "INR" ? "rupee" : "dollar"}</span>
      </div>
      {/* R38: two columns: the label (it may wrap) with who gets it under it, the amount (never wraps) */}
      <dl className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3 gap-y-2">
        {rows.map((r, i) => (
          <React.Fragment key={i}>
            <dt className={cn(r.accent && "font-semibold text-peacock")}>
              <span className="block">{r.label}</span>
              <span className="block text-small font-normal text-muted">{r.payee}</span>
            </dt>
            <dd className={cn("whitespace-nowrap text-right", r.accent && "font-semibold text-peacock")}>
              {r.struck ? (<><s className="text-faint">{r.struck}</s> <b>{r.amount}</b></>) : r.amount}
            </dd>
          </React.Fragment>
        ))}
      </dl>
      <div className="mt-3 flex justify-between border-t-[1.5px] border-dashed border-line-strong pt-3 text-h3">
        <span>{totalLabel}</span>
        <span>{money(billTotal(lines), currency)}</span>
      </div>
    </section>
  );
}
