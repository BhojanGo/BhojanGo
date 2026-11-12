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
    <section aria-label="The fair bill" className={cn("rounded-card bg-white p-4 text-sm tabular-nums", className)}>
      <div className="mb-2.5 flex items-baseline justify-between">
        <span className="font-display text-lg font-semibold">The fair bill</span>
        <span className="text-xs font-bold text-peacock">who gets each {currency === "INR" ? "rupee" : "dollar"}</span>
      </div>
      <dl className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-baseline gap-x-2.5 gap-y-2">
        {rows.map((r, i) => (
          <React.Fragment key={i}>
            <dt className={cn(r.accent && "font-semibold text-peacock")}>{r.label}</dt>
            <dd className="text-[11px] font-bold text-muted">{r.payee}</dd>
            <dd className={cn("text-right", r.accent && "font-semibold text-peacock")}>
              {r.struck ? (<><s className="text-faint">{r.struck}</s> <b>{r.amount}</b></>) : r.amount}
            </dd>
          </React.Fragment>
        ))}
      </dl>
      <div className="mt-3 flex justify-between border-t-[1.5px] border-dashed border-line-strong pt-3 text-lg font-extrabold">
        <span>{totalLabel}</span>
        <span>{money(billTotal(lines), currency)}</span>
      </div>
    </section>
  );
}
