// "Who gets your money" (R6): the shares of a real bill (the engine's lines, e.g.
// GET /pricing/example for the country's city), as whole percentages that add up
// to exactly 100. Pure: the apps can mirror it line for line.

export interface SplitLine {
  code: string;
  amount: string | number;
  funded_by?: string | null;
}

export type Payee = "kitchen" | "rider" | "tax" | "us";

// Who each line goes to: the delivery and service fees are ours (riders are
// paid separately), tax is the government's, the tip is all the rider's.
export const PAYEE: Record<string, Payee> = {
  food: "kitchen", packaging: "kitchen", delivery_fee: "us", service_fee: "us", small_order_fee: "us",
  surge: "us", late_night_fee: "us", tax: "tax", tip: "rider",
};

export const PAYEES: readonly Payee[] = ["kitchen", "rider", "tax", "us"];

export function payeeOf(line: SplitLine): Payee {
  if (line.code === "promotion") return line.funded_by === "restaurant" ? "kitchen" : "us";
  return PAYEE[line.code] ?? "us";
}

/**
 * Sums per payee (a promotion lowers whoever funds it; a negative sum counts as 0)
 * and whole percentages by largest remainder, so they always add up to 100.
 * Null for an empty or zero bill.
 */
export function fairSplit(lines: readonly SplitLine[]): { payee: Payee; amount: number; percent: number }[] | null {
  const sums: Record<Payee, number> = { kitchen: 0, rider: 0, tax: 0, us: 0 };
  for (const ln of lines) sums[payeeOf(ln)] += Number(ln.amount) || 0;
  const amounts = PAYEES.map((p) => Math.max(sums[p], 0));
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
