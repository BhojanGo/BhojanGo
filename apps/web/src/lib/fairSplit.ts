// "Who gets your money" (R6, R7): the shares of a real bill as whole percentages that
// add up to exactly 100. The amounts are the engine's split of the bill (GET
// /pricing/example's "shares"): the kitchen's payout, the rider's pay (base +
// distance + wait) plus the tip, the tax, and what is left for BhojanGo. Nothing is
// worked out from the bill's lines here: a delivery fee is not the rider's pay.
// Pure: the apps can mirror it line for line.

export type Payee = "kitchen" | "rider" | "tax" | "us";

export const PAYEES: readonly Payee[] = ["kitchen", "rider", "tax", "us"];

export type Shares = Record<Payee, string | number>;

export interface SplitLine {
  code: string;
  amount: string | number;
  funded_by?: string | null;
}

// The fair bill's tag on each line (who the customer pays it to): the delivery and
// service fees are ours, tax is the government's, the tip is all the rider's. Only
// for the per-line tags; the shares come from the engine's split (rider pay comes
// out of our fees).
export const PAYEE: Record<string, Payee> = {
  food: "kitchen", packaging: "kitchen", delivery_fee: "us", platform_fee: "us", service_fee: "us", small_order_fee: "us",
  surge: "us", late_night_fee: "us", tax: "tax", tip: "rider",
};

/** R29 fee model v2 (a bill with a platform fee line): the delivery fee is all the delivery partner's. */
export function payeeOf(line: SplitLine, lines: readonly SplitLine[] = []): Payee {
  if (line.code === "promotion") return line.funded_by === "restaurant" ? "kitchen" : "us";
  if (line.code === "delivery_fee" && lines.some((l) => l.code === "platform_fee")) return "rider";
  return PAYEE[line.code] ?? "us";
}

/**
 * Whole percentages by largest remainder, so they always add up to 100 (a share
 * below zero, e.g. BhojanGo losing money on an order, counts as 0).
 * Null for missing shares or a zero bill.
 */
export function fairSplit(shares: Partial<Shares> | null | undefined): { payee: Payee; amount: number; percent: number }[] | null {
  if (!shares) return null;
  const amounts = PAYEES.map((p) => Math.max(Number(shares[p]) || 0, 0));
  const total = amounts.reduce((a, b) => a + b, 0);
  if (!(total > 0)) return null;
  const exact = amounts.map((a) => (a / total) * 100);
  const percent = exact.map(Math.floor);
  let left = 100 - percent.reduce((a, b) => a + b, 0);
  // the largest remainders get the leftover points (ties: the earlier payee)
  const order = exact.map((x, i) => [x - Math.floor(x), i] as const).sort((a, b) => b[0] - a[0] || a[1] - b[1]);
  for (const [, i] of order) {
    if (left <= 0) break;
    percent[i]! += 1;
    left -= 1;
  }
  return PAYEES.map((payee, i) => ({ payee, amount: Math.round(amounts[i]! * 100) / 100, percent: percent[i]! }));
}
