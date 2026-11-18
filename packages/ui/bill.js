// The fair bill (P8 bill lines → what each row says and who gets the money).
// Shared by web and the apps; no DOM, no React Native.

// Who gets each line, in the words people read: KITCHEN, DELIVERY PARTNER, TAX,
// BHOJANGO. A line is DELIVERY PARTNER only when all of it goes to them (the tip).
// The delivery fee is BhojanGo's: delivery partners are paid separately (base,
// distance, waiting, the floor).
const PAYEE = {
  food: "KITCHEN", packaging: "KITCHEN",
  delivery_fee: "BHOJANGO",
  service_fee: "BHOJANGO", small_order_fee: "BHOJANGO", surge: "BHOJANGO", late_night_fee: "BHOJANGO",
  tax: "TAX", tip: "DELIVERY PARTNER",
};

const SYMBOL = { INR: "₹", USD: "$" };

/** ₹1,24,050.00 (Indian grouping) or $1,240.50; −₹50.00 for discounts. Always two decimals (R12). */
function money(amount, currency) {
  const n = Number(amount);
  const sign = n < 0 ? "−" : "";
  const abs = Math.abs(n);
  const decimals = 2;
  const locale = currency === "INR" ? "en-IN" : "en-US";
  const body = abs.toLocaleString(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  return `${sign}${SYMBOL[currency] ?? currency + " "}${body}`;
}

// What a person reads for each payee code (the codes stay: PAYEE, funded_by).
const PAYEE_LABEL = { KITCHEN: "Kitchen", BHOJANGO: "BhojanGo", TAX: "Tax", "DELIVERY PARTNER": "Delivery partner" };

/** A line of 0 (a tax of $0.00, a free fee) is not shown (R12); the total still counts every line. */
function shownLines(lines) {
  return lines.filter((ln) => Math.abs(Number(ln.amount)) >= 0.005);
}

/**
 * Rows for the fair bill from the API's bill lines ({code, label, amount,
 * funded_by, detail}). Each row: {label, payee, amount, accent, struck}.
 * - discounts show who funded them (BHOJANGO or KITCHEN) in Peacock
 * - free delivery (a delivery fee plus an offer of minus that fee) is one row:
 *   the usual fee struck through, then 0, paid by the kitchen or by us
 */
function billRows(lines, currency) {
  const delivery = lines.find((ln) => ln.code === "delivery_fee");
  const freeDelivery = delivery && lines.find((ln) => ln.code === "promotion" &&
    Math.abs(Number(ln.amount) + Number(delivery.amount)) < 0.005 && Number(delivery.amount) > 0);
  const rows = [];
  for (const ln of shownLines(lines)) {
    if (ln === freeDelivery) continue;
    const amount = Number(ln.amount);
    if (ln === delivery && freeDelivery) {
      rows.push({ label: ln.label, payee: freeDelivery.funded_by === "restaurant" ? "Kitchen's treat" : "On us",
                  amount: money(0, currency), struck: money(amount, currency) });
    } else if (ln.code === "promotion") {
      rows.push({ label: ln.label, payee: PAYEE_LABEL[ln.funded_by === "restaurant" ? "KITCHEN" : "BHOJANGO"],
                  amount: money(amount, currency), accent: true });
    } else {
      rows.push({ label: ln.label, payee: PAYEE_LABEL[PAYEE[ln.code] ?? "BHOJANGO"], amount: money(amount, currency) });
    }
  }
  return rows;
}

function billTotal(lines) {
  return lines.reduce((sum, ln) => sum + Number(ln.amount), 0);
}

module.exports = { money, billRows, billTotal, shownLines, PAYEE };
