// The fair bill (P8 bill lines → what each row says and who gets the money).
// Shared by web and the apps; no DOM, no React Native.

// Who gets each line, in the words people read: KITCHEN, DELIVERY PARTNER, TAX,
// BHOJANGO. A line is DELIVERY PARTNER only when all of it goes to them (the tip).
// Before R29 the delivery fee was BhojanGo's (partners were paid separately: base,
// distance, waiting, the floor). R29 fee model v2 (a bill with a platform fee line):
// the delivery fee goes 100% to the delivery partner, the platform fee to BhojanGo.
const PAYEE = {
  food: "KITCHEN", packaging: "KITCHEN",
  delivery_fee: "BHOJANGO", platform_fee: "BHOJANGO",
  service_fee: "BHOJANGO", small_order_fee: "BHOJANGO", surge: "BHOJANGO", late_night_fee: "BHOJANGO",
  tax: "TAX", tip: "DELIVERY PARTNER",
};

/** Who gets this line of this bill (a payee code above). */
function payeeOf(line, lines) {
  if (line.code === "delivery_fee" && (lines || []).some((ln) => ln.code === "platform_fee")) return "DELIVERY PARTNER";
  return PAYEE[line.code] ?? "BHOJANGO";
}

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
const PAYEE_LABEL = { KITCHEN: "Restaurant", BHOJANGO: "BhojanGo", TAX: "Tax", "DELIVERY PARTNER": "Delivery partner" };

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
      rows.push({ label: ln.label, payee: freeDelivery.funded_by === "restaurant" ? "Restaurant's treat" : "On us",
                  amount: money(0, currency), struck: money(amount, currency) });
    } else if (ln.code === "promotion") {
      rows.push({ label: ln.label, payee: PAYEE_LABEL[ln.funded_by === "restaurant" ? "KITCHEN" : "BHOJANGO"],
                  amount: money(amount, currency), accent: true });
    } else {
      rows.push({ label: ln.label, payee: PAYEE_LABEL[payeeOf(ln, lines)], amount: money(amount, currency) });
    }
  }
  return rows;
}

function billTotal(lines) {
  return lines.reduce((sum, ln) => sum + Number(ln.amount), 0);
}

const REFUND_REASONS = ["missing_item", "wrong_item", "quality", "late", "damaged_in_transit", "rider_issue", "goodwill",
  "full", "cancelled", "other"];

/**
 * R27: a receipt's refunds, from GET /pricing/orders/{id}/bill (refunds, paid): each with the reason
 * to name (a whole-order refund on a cancelled order is "cancelled"), and what was paid after them.
 * Shared by the website's and the customer app's receipt; the PDF says the same (orders/service/receipt.py).
 */
function receiptRefunds(bill, cancelled) {
  const refunds = (bill.refunds || []).map((r) => {
    let reason = REFUND_REASONS.includes(r.reason) ? r.reason : "other";
    if (reason === "full" && cancelled) reason = "cancelled";
    return { amount: Number(r.amount), reason, items: r.items || [] };
  });
  const refunded = refunds.reduce((sum, r) => sum + r.amount, 0);
  const paid = bill.paid != null ? Number(bill.paid) : Math.max(0, Math.round((Number(bill.total) - refunded) * 100) / 100);
  return { refunds, refunded, paid };
}

module.exports = { money, billRows, billTotal, shownLines, receiptRefunds, REFUND_REASONS, PAYEE, payeeOf };
