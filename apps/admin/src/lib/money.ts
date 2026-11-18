// The admin console's money formatter: pure (no React, no imports), so `node --test`
// covers it and everything built on it (test/*.test.ts).

/**
 * An amount in a currency, the way `locale` writes it (₹1,24,050.00 in en-IN, $1,240.50
 * in en-US). Pass the country's first Markets locale; without one the currency's
 * usual locale is used.
 */
export function money(v: number | string | null | undefined, currency: string, decimals = 2, locale?: string): string {
  const n = Number(v ?? 0);
  const loc = locale ?? (currency === "INR" ? "en-IN" : "en-US");
  try {
    return n.toLocaleString(loc, { style: "currency", currency, maximumFractionDigits: decimals, minimumFractionDigits: decimals });
  } catch {
    return `${currency} ${n.toFixed(decimals)}`; // an unknown currency code
  }
}
