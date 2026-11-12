// The fair bill (P8 bill lines → what each row says and who gets the money).
// Shared by web and the apps; no DOM, no React Native.

const PAYEE = {
  food: "KITCHEN", packaging: "KITCHEN",
  delivery_fee: "RIDER",
  service_fee: "US", small_order_fee: "US", surge: "US", late_night_fee: "US",
  tax: "GOVT", tip: "RIDER",
};

const SYMBOL = { INR: "₹", USD: "$" };

/** ₹1,24,050.00 (Indian grouping) or $1,240.50; −₹50.00 for discounts. */
function money(amount, currency, { decimals = 2 } = {}) {
  const n = Number(amount);
  const sign = n < 0 ? "−" : "";
  const abs = Math.abs(n);
  const locale = currency === "INR" ? "en-IN" : "en-US";
  const body = abs.toLocaleString(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  return `${sign}${SYMBOL[currency] ?? currency + " "}${body}`;
}

/**
 * Rows for the fair bill from the API's bill lines ({code, label, amount,
 * funded_by, detail}). Each row: {label, payee, amount, accent, struck}.
 * - discounts show who funded them (US or KITCHEN) in Peacock
 * - free delivery (a delivery fee plus an offer of minus that fee) is one row:
 *   the usual fee struck through, then 0, paid by the kitchen or by us
 */
function billRows(lines, currency) {
  const delivery = lines.find((ln) => ln.code === "delivery_fee");
  const freeDelivery = delivery && lines.find((ln) => ln.code === "promotion" &&
    Math.abs(Number(ln.amount) + Number(delivery.amount)) < 0.005 && Number(delivery.amount) > 0);
  const rows = [];
  for (const ln of lines) {
    if (ln === freeDelivery) continue;
    const amount = Number(ln.amount);
    if (ln === delivery && freeDelivery) {
      rows.push({ label: ln.label, payee: freeDelivery.funded_by === "restaurant" ? "KITCHEN'S TREAT" : "ON US",
                  amount: money(0, currency, { decimals: 0 }), struck: money(amount, currency, { decimals: 0 }) });
    } else if (ln.code === "promotion") {
      rows.push({ label: ln.label, payee: ln.funded_by === "restaurant" ? "KITCHEN" : "US",
                  amount: money(amount, currency), accent: true });
    } else {
      rows.push({ label: ln.label, payee: PAYEE[ln.code] ?? "US", amount: money(amount, currency) });
    }
  }
  return rows;
}

function billTotal(lines) {
  return lines.reduce((sum, ln) => sum + Number(ln.amount), 0);
}

module.exports = { money, billRows, billTotal, PAYEE };
